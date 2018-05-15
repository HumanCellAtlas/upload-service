
from .batch_job import BatchJobDumper
from .db_dumper import DbDumper


class DiagnosticsCLI:

    @classmethod
    def configure(cls, subparsers):
        diag_parser = subparsers.add_parser('diag', description="Retrieve diagnostic information")
        diag_parser.set_defaults(command='diag')
        diag_subparsers = diag_parser.add_subparsers()

        job_parser = diag_subparsers.add_parser('job', description="Get information about Batch jobs")
        job_parser.set_defaults(command='diag', diag_command='job')
        job_parser.add_argument('job_id', nargs='?', help="Show data bout this Batch job")

        job_parser = diag_subparsers.add_parser('db', description="Dump database records")
        job_parser.set_defaults(command='diag', diag_command='db')
        job_parser.add_argument('upload_area_id', nargs='?', help="Show record for this upload area")
        job_parser.add_argument('filename', nargs='?', help="Show record for this file in the upload area")

    @classmethod
    def run(cls, args):
        if args.diag_command == 'job':
            BatchJobDumper().describe_job(args.job_id)
        elif args.diag_command == 'db':
            if args.upload_area_id:
                DbDumper().dump_one_area(args.upload_area_id, args.filename)
            else:
                DbDumper().dump_all()
