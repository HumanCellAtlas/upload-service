import os

from upload.common.batch import JobDefinition
from .upload_cleaner import UploadCleaner


class CleanupCLI:

    @classmethod
    def configure(cls, subparsers):
        cleanup_parser = subparsers.add_parser('cleanup', description="Clean Things Up")
        cleanup_subparsers = cleanup_parser.add_subparsers()

        cleanup_areas_parser = cleanup_subparsers.add_parser('areas')
        cleanup_areas_parser.set_defaults(command='cleanup', cleanup_command='areas')
        cleanup_areas_parser.add_argument('--age-days', type=int, default=3, help="delete areas older than this")
        cleanup_areas_parser.add_argument('--ignore-file-age', action='store_true', help="ignore age of files in bucket")
        cleanup_areas_parser.add_argument('--dry-run', action='store_true', help="examine but don't take action")

        cleanup_jobdefs_parser = cleanup_subparsers.add_parser('jobdefs')
        cleanup_jobdefs_parser.set_defaults(command='cleanup', cleanup_command='jobdefs')

    @classmethod
    def run(cls, args):
        if args.cleanup_command == 'areas':
            UploadCleaner(os.environ['DEPLOYMENT_STAGE'],
                          clean_older_than_days=args.age_days,
                          ignore_file_age=args.ignore_file_age,
                          dry_run=args.dry_run)

        elif args.cleanup_command == 'jobdefs':
            ndeleted = JobDefinition.clear_all()
            print(f"{ndeleted} Job Definitions deleted")
