import os

from upload.common.batch import JobDefinition
from .upload_cleaner import UploadCleaner


class CleanupCLI:

    @classmethod
    def configure(cls, subparsers):
        cleanup_parser = subparsers.add_parser('cleanup', description="Clean Things Up")
        cleanup_subparsers = cleanup_parser.add_subparsers()

        cleanup_files_parser = cleanup_subparsers.add_parser('files')
        cleanup_files_parser.set_defaults(command='cleanup', cleanup_command='files')
        cleanup_files_parser.add_argument('-j', '--jobs', nargs='?', help="parallelize", type=int, default=1)

    @classmethod
    def run(cls, args):
        if args.cleanup_command == 'files':
            UploadCleaner(options=args).clean_files()
