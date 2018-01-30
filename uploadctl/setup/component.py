import sys

indent_level = 0


def indent():
    return indent_level * 2 * " "


class ExternalControl(RuntimeError):
    pass


class AbortComposite(RuntimeError):
    pass


class Component:

    SETUP_WORD = "CREATED"
    TEARDOWN_WORD = "DELETED"
    MISSING_WORD = "MISSING"

    def __init__(self, **options):
        quiet = options.get('quiet', False)
        global indent_level
        if not quiet:
            sys.stdout.write("%s%-90s " % (indent(), str(self)))
            sys.stdout.flush()

    def setup(self):
        if self.is_setup():
            print("ok")
        else:
            try:
                self.set_it_up()
                if self.is_setup():
                    print(self.SETUP_WORD)
                else:
                    print("SETUP FAILED")
                    exit(1)
            except ExternalControl as e:
                print(e)
                raise AbortComposite()

    def check(self):
        if self.is_setup():
            print("ok")
        else:
            print(self.MISSING_WORD)

    def teardown(self):
        if self.is_setup():
            try:
                self.tear_it_down()
                if self.is_setup():
                    print("TEARDOWN FAILED")
                    exit(1)
                else:
                    print(self.TEARDOWN_WORD)
            except ExternalControl as e:
                print(e)
        else:
            print("-")

    def is_setup(self):
        raise NotImplementedError

    def set_it_up(self):
        raise NotImplementedError

    def tear_it_down(self):
        raise NotImplementedError


class AttributeComponent(Component):

    SETUP_WORD = "ENABLED"
    TEARDOWN_WORD = "DISABLED"
    MISSING_WORD = "DISABLED"


class CompositeComponent:

    SUBCOMPONENTS = {}

    def __init__(self, **options):
        self.options = options
        if str(self) is not '':
            print(indent() + str(self))

    def setup(self):
        self._apply_action('setup')

    def check(self):
        self._apply_action('check')

    def teardown(self):
        self._apply_action('teardown', reverse_order=True)

    def _apply_action(self, action, reverse_order=False):
        global indent_level
        indent_level += 1
        components = list(self.SUBCOMPONENTS)
        if reverse_order:
            components.reverse()
        try:
            for component in components:
                self._apply_action_to_component(component, action)
        except AbortComposite:
            pass
        indent_level -= 1

    def _apply_action_to_component(self, component_name, action):
        component_class = self.SUBCOMPONENTS[component_name]
        component = component_class(**self.options)
        action_func = getattr(component, action)
        action_func()
