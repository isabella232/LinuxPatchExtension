import datetime
from src.Constants import Constants


class EnableCommandHandler(object):
    """ Responsible for executing the action for enable command """
    def __init__(self, logger, utility, runtime_context_handler, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time, seq_no):
        self.logger = logger
        self.utility = utility
        self.runtime_context_handler = runtime_context_handler
        self.ext_env_handler = ext_env_handler
        self.ext_config_settings_handler = ext_config_settings_handler
        self.core_state_handler = core_state_handler
        self.ext_state_handler = ext_state_handler
        self.ext_output_status_handler = ext_output_status_handler
        self.process_handler = process_handler
        self.cmd_exec_start_time = cmd_exec_start_time
        self.seq_no = seq_no
        self.config_public_settings = Constants.ConfigPublicSettingsFields
        self.core_state_fields = Constants.CoreStateFields
        self.status = Constants.Status

    def execute_handler_action(self):
        """ Responsible for taking appropriate action for enable command as per the request sent in Handler Configuration file by user """
        try:
            config_settings = self.ext_config_settings_handler.read_file(self.seq_no)
            prev_patch_max_end_time = self.cmd_exec_start_time + datetime.timedelta(hours=0, minutes=Constants.ENABLE_MAX_RUNTIME)
            self.ext_state_handler.create_file(self.seq_no, config_settings.__getattribute__(self.config_public_settings.operation), prev_patch_max_end_time)
            core_state_content = self.core_state_handler.read_file()

            # if NoOperation is requested, terminate all running processes from previous operation and update status file
            if config_settings.__getattribute__(self.config_public_settings.operation) == Constants.NOOPERATION:
                self.process_nooperation(config_settings, core_state_content)
            else:
                # if any of the other operations are requested, verify if request is a new request or a re-enable, by comparing sequence number from the prev request and current one
                if core_state_content is None or core_state_content.__getattribute__(self.core_state_fields.number) is None:
                    # first patch request for the VM
                    self.logger.log("No state information was found for any previous patch operation. Launching a new patch operation.")
                    self.launch_new_process(config_settings, create_status_output_file=True)
                else:
                    if int(core_state_content.__getattribute__(self.core_state_fields.number)) != int(self.seq_no):
                        # new request
                        self.process_enable_request(config_settings, prev_patch_max_end_time, core_state_content)
                    else:
                        # re-enable request
                        self.process_reenable_request(config_settings, core_state_content)
        except Exception as error:
            self.logger.log_error("Failed to execute enable. [Exception={0}]".format(repr(error)))
            raise

    def process_enable_request(self, config_settings, prev_patch_max_end_time, core_state_content):
        """ Called when the current request is different from the one before. Identifies and waits for the previous request action to complete, if required before addressing the current request """
        self.logger.log("Terminating older patch operation, if still in progress, as per it's completion duration and triggering the new requested patch opertaion.")
        self.runtime_context_handler.process_previous_patch_operation(self.core_state_handler, self.process_handler, prev_patch_max_end_time, core_state_content)
        self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file)
        self.launch_new_process(config_settings, create_status_output_file=True)

    def process_reenable_request(self, config_settings, core_state_content):
        """ Called when the current request has the same config as the one before it. Restarts the operation if the previous request has errors, no action otherwise """
        self.logger.log("This is the same request as the previous patch operation. Checking previous request's status")
        if core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'false':
            running_process_ids = self.process_handler.identify_running_processes(core_state_content.__getattribute__(self.core_state_fields.process_ids))
            if len(running_process_ids) == 0:
                self.logger.log("Re-triggering the patch operation as the previous patch operation was not running and hadn't marked completion either.")
                self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file)
                self.launch_new_process(config_settings, create_status_output_file=False)
            else:
                self.logger.log("Patch operation is in progress from the previous request. [Operation={0}]".format(config_settings.__getattribute__(self.config_public_settings.operation)))
                exit(Constants.ExitCode.Okay)

        else:
            self.logger.log("Patch operation already completed in the previous request. [Operation={0}]".format(config_settings.__getattribute__(self.config_public_settings.operation)))
            exit(Constants.ExitCode.Okay)

    def launch_new_process(self, config_settings, create_status_output_file):
        """ Creates <sequence number>.status to report the current request's status and launches core code to handle the requested operation """
        # create Status file
        if create_status_output_file:
            self.ext_output_status_handler.write_status_file(config_settings.__getattribute__(self.config_public_settings.operation), status=self.status.Transitioning.lower())
        else:
            self.ext_output_status_handler.update_file(self.seq_no, self.ext_env_handler.status_folder)
        # launch core code in a process and exit extension handler
        process = self.process_handler.start_daemon(self.seq_no, config_settings, self.ext_env_handler)
        self.logger.log("exiting extension handler")
        exit(Constants.ExitCode.Okay)

    def process_nooperation(self, config_settings, core_state_content):
        self.logger.log("NoOperation requested. Terminating older patch operation, if still in progress.")
        self.ext_output_status_handler.set_current_operation(Constants.NOOPERATION)
        activity_id = config_settings.__getattribute__(self.config_public_settings.activity_id)
        operation = config_settings.__getattribute__(self.config_public_settings.operation)
        start_time = config_settings.__getattribute__(self.config_public_settings.start_time)
        try:
            self.ext_output_status_handler.set_nooperation_substatus_json(operation, activity_id, start_time, status=Constants.Status.Transitioning)
            self.runtime_context_handler.terminate_processes_from_previous_operation(self.process_handler, core_state_content)
            self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file, raise_if_not_found=False)
            # ToDo: log prev activity id later
            self.ext_output_status_handler.set_nooperation_substatus_json(operation, activity_id, start_time, status=Constants.Status.Success)
            self.logger.log("exiting extension handler")
            exit(Constants.ExitCode.Okay)
        except Exception as error:
            error_msg = "Error executing NoOperation: " + repr(error)
            self.logger.log(error_msg)
            if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                self.ext_output_status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            else:
                self.ext_output_status_handler.add_error_to_status("Error executing NoOperation due to last reported error.", Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            self.ext_output_status_handler.set_nooperation_substatus_json(operation, activity_id, start_time, status=Constants.Status.Error)

