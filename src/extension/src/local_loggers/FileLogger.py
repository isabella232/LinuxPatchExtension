import os
import sys
from src.Constants import Constants


class FileLogger(object):
    """Facilitates writing selected logs to a file"""

    def __init__(self, log_folder, log_file):
        # opening/creating the log file
        try:
            self.log_file_path = os.path.join(log_folder, log_file)
            self.log_file_handle = open(self.log_file_path, "a")
        except Exception as error:
            sys.stdout.write("FileLogger - Error opening file. [File={0}] [Exception={1}]".format(self.log_file_path, repr(error)))

        # Retaining 10 most recent log files, deleting others
        self.delete_older_log_files(log_folder)
        # verifying if the log file retention was applied.
        log_files = self.get_all_log_files(log_folder)
        if len(log_files) > Constants.MAX_LOG_FILES_ALLOWED:
            print("Retention failed for log files")
            raise Exception("Retention failed for log files")

    def __del__(self):
        self.close()

    def get_all_log_files(self, log_folder):
        """ Returns all files with .log extension within the given folder"""
        return [os.path.join(log_folder, file) for file in os.listdir(log_folder) if (file.lower().endswith('.log'))]

    def delete_older_log_files(self, log_folder):
        """ deletes older log files, retaining only the last 10 log files """
        print("Retaining " + str(Constants.LOG_FILES_TO_RETAIN) + " most recent operation logs, deleting others.")
        try:
            log_files = self.get_all_log_files(log_folder)
            log_files.sort(key=os.path.getmtime, reverse=True)
        except Exception as e:
            print("Error identifying log files to delete. [Exception={0}]".format(repr(e)))
            return

        if len(log_files) >= Constants.LOG_FILES_TO_RETAIN:
            for file in log_files[Constants.LOG_FILES_TO_RETAIN:]:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                        print("Deleted [File={0}]".format(repr(file)))
                except Exception as e:
                    print("Error deleting log file. [File={0} [Exception={1}]]".format(repr(file), repr(e)))

    def write(self, message, fail_silently=True):
        try:
            if self.log_file_handle is not None:
                self.log_file_handle.write(message)
            else:
                raise Exception("Log file not found")
        except IOError:
            # DO NOT write any errors here to stdout
            if not fail_silently:
                raise
        except ValueError as error:
            sys.stdout.write("FileLogger - [Error={0}]".format(repr(error)))
        except Exception as error:
            sys.stdout.write("FileLogger - Error opening file. [File={0}] [Exception={1}]".format(self.log_file_path, repr(error)))

    def flush(self):
        if self.log_file_handle is not None:
            self.log_file_handle.flush()

    def close(self):
        if self.log_file_handle is not None:
            self.log_file_handle.close()