# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

import datetime
import json
import os
import time
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.src.bootstrap.Bootstrapper import Bootstrapper
from core.src.bootstrap.Constants import Constants


class RuntimeCompositor(object):
    def __init__(self, argv=Constants.DEFAULT_UNSPECIFIED_VALUE, legacy_mode=False, package_manager_name=Constants.APT):
        # Init data
        self.current_env = Constants.DEV
        os.environ[Constants.LPE_ENV_VARIABLE] = self.current_env
        self.argv = argv if argv != Constants.DEFAULT_UNSPECIFIED_VALUE else ArgumentComposer().get_composed_arguments()

        # Overriding time.sleep to avoid delays in test execution
        time.sleep = self.mock_sleep

        # Adapted bootstrapper
        bootstrapper = Bootstrapper(self.argv, capture_stdout=False)

        # Reconfigure env layer for legacy mode tests
        self.env_layer = bootstrapper.env_layer
        if legacy_mode:
            self.legacy_env_layer_extensions = LegacyEnvLayerExtensions(package_manager_name)
            self.reconfigure_env_layer_to_legacy_mode()

        # Core components
        self.container = bootstrapper.build_out_container()
        self.file_logger = bootstrapper.file_logger
        self.composite_logger = bootstrapper.composite_logger
        self.lifecycle_manager, self.telemetry_writer, self.status_handler = bootstrapper.build_core_components(self.container)

        # Business logic components
        self.execution_config = self.container.get('execution_config')
        self.package_manager = self.container.get('package_manager')
        self.reboot_manager = self.container.get('reboot_manager')
        self.reconfigure_reboot_manager()
        self.package_filter = self.container.get('package_filter')
        self.patch_assessor = self.container.get('patch_assessor')
        self.patch_installer = self.container.get('patch_installer')
        self.maintenance_window = self.container.get('maintenance_window')

        # Extension handler dependency
        self.write_ext_state_file(self.lifecycle_manager.ext_state_file_path, self.execution_config.sequence_number, datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), self.execution_config.operation)

    def stop(self):
        self.telemetry_writer.close_transports()
        self.file_logger.close(message_at_close="<Runtime stopped>")
        self.container.reset()

    @staticmethod
    def write_ext_state_file(path, sequence_number, achieve_enable_by, operation):
        data = {
            "extensionSequence": {
                "number": sequence_number,
                "achieveEnableBy": achieve_enable_by,
                "operation": operation
            }
        }
        with open(path, "w+") as file_handle:
            file_handle.write(json.dumps(data))

    def set_legacy_test_type(self, test_type):
        self.legacy_env_layer_extensions.legacy_test_type = test_type

    def reconfigure_env_layer_to_legacy_mode(self):
        self.env_layer.get_package_manager = self.legacy_env_layer_extensions.get_package_manager
        self.env_layer.platform = self.legacy_env_layer_extensions.LegacyPlatform()
        self.env_layer.set_legacy_test_mode()
        self.env_layer.run_command_output = self.legacy_env_layer_extensions.run_command_output
        self.env_layer.check_sudo_status = self.legacy_env_layer_extensions.check_sudo_status

    def reconfigure_reboot_manager(self):
        self.reboot_manager.start_reboot = self.start_reboot

    def start_reboot(self, message="Test initiated reboot mock"):
        self.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)

    def mock_sleep(self, seconds):
        pass

    @staticmethod
    def write_to_file(path, data):
        with open(path, "w+") as file_handle:
            file_handle.write(data)

