from .conductor import SetupConductor


class SetupCLI:

    @classmethod
    def configure(cls, subparsers):
        setup_parser = subparsers.add_parser('setup')
        setup_parser.set_defaults(command='setup')
        setup_parser.add_argument('component', nargs='?', choices=list(SetupConductor.SUBCOMPONENTS.keys()))
        setup_parser.add_argument('--ami', type=str, metavar="ID",
                                  help="AMI to use for validation batch compute env setup")
        setup_parser.add_argument('--ec2-key-pair', type=str, metavar="KEYNAME",
                                  help="Key pair to use for validation batch compute env setup")
        setup_parser.add_argument('--security-groups', type=str, metavar="GROUPS", default='default',
                                  help="Comma-separated list of EC2 security groups to use"
                                       " for validation batch compute env setup")

        check_parser = subparsers.add_parser('check')
        check_parser.set_defaults(command='check')
        check_parser.add_argument('component', nargs='?', choices=list(SetupConductor.SUBCOMPONENTS.keys()))

        teardown_parser = subparsers.add_parser('teardown')
        teardown_parser.set_defaults(command='teardown')
        teardown_parser.add_argument('component', nargs='?', choices=list(SetupConductor.SUBCOMPONENTS.keys()))

    @classmethod
    def run(cls, args):
        if args.component:
            component = SetupConductor.SUBCOMPONENTS[args.component](**vars(args))
            getattr(component, args.command)()
        else:
            setup = SetupConductor(**vars(args))
            getattr(setup, args.command)()
