
class ChecksumDaemon:

    def __init__(self, context):
        self._context = context
        self.log("Ahm ahliiivvve!")

    def consume_event(self, event):
        self.log(f"Consume_event, {event}")

    def log(self, message):
        self._context.log(message)
