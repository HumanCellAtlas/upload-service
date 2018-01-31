import os

from .upload_cleaner import UploadCleaner


class CleanupCLI:

    @classmethod
    def configure(cls, subparsers):
        cleanup_parser = subparsers.add_parser('cleanup', description="Remove old Upload Areas")
        cleanup_parser.set_defaults(command='cleanup')
        cleanup_parser.add_argument('--age-days', type=int, default=3, help="delete areas older than this")
        cleanup_parser.add_argument('--ignore-file-age', action='store_true', help="ignore age of files in bucket")
        cleanup_parser.add_argument('--dry-run', action='store_true', help="examine but don't take action")

    @classmethod
    def run(cls, args):
        UploadCleaner(os.environ['DEPLOYMENT_STAGE'],
                      clean_older_than_days=args.age_days,
                      ignore_file_age=args.ignore_file_age,
                      dry_run=args.dry_run)
