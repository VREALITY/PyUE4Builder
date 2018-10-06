#!/usr/bin/env python

import os
import contextlib
import re
from utility.common import launch, error_exit
from actions.action import Action

__author__ = "Ryan Sheffer"
__copyright__ = "Copyright 2018, Ryan Sheffer Open Source"
__credits__ = ["Ryan Sheffer", "VREAL"]


class Versionrc(Action):
    """
    Updates the version RC within the output executable so the executable is acceptable to the VReal tray app
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.cur_build_type = 0
        build_meta = kwargs['build_meta'] if 'build_meta' in kwargs else None
        if build_meta is not None and getattr(build_meta, 'cur_build_type', None) is not None:
            self.cur_build_type = build_meta.cur_build_type

        self.ResourceEditorPath = kwargs['ResourceEditorPath'] if 'ResourceEditorPath' in kwargs else ''
        self.ResourceCompilerPath = kwargs['ResourceCompilerPath'] if 'ResourceCompilerPath' in kwargs else ''
        self.ResourceHackerPath = kwargs['ResourceHackerPath'] if 'ResourceHackerPath' in kwargs else ''

        self.vrl_project_fingerprint = kwargs['vrl_project_fingerprint'] if 'vrl_project_fingerprint' in kwargs else ''
        self.vrl_sdk_version = kwargs['vrl_sdk_version'] if 'vrl_sdk_version' in kwargs else ''
        self.vrl_project_name = kwargs['vrl_project_name'] if 'vrl_project_name' in kwargs else ''
        self.vrl_project_description = kwargs['vrl_project_description'] if 'vrl_project_description' in kwargs else ''
        self.vrl_company_name = kwargs['vrl_company_name'] if 'vrl_company_name' in kwargs else ''

    def verify(self):
        if self.vrl_project_fingerprint == '':
            return 'vrl_project_fingerprint not set!'
        if self.vrl_sdk_version == '':
            return 'vrl_sdk_version not set!'
        if self.vrl_project_name == '':
            return 'vrl_project_name not set!'
        if self.vrl_project_description == '':
            return 'vrl_project_description not set!'
        if self.vrl_company_name == '':
            return 'vrl_company_name not set!'
        if self.cur_build_type == '':
            return 'Version RC requires an argument called cur_build_type which contains what type of build was' \
                   'performed by the previous package command. See the build_type parameter in the action' \
                   'Package for details. You can pass that variable using meta data OR just pass in an argument' \
                   'to this action with the necessary string.'

        return ''

    def run(self):
        self.error = self.verify()
        if self.error != '':
            return False

        with contextlib.suppress(FileNotFoundError):
            os.unlink('.\\tmpversioninfo.rc')

        with contextlib.suppress(FileNotFoundError):
            os.unlink('.\\versionOverwrite.log')

        windows_folder_name = 'WindowsNoEditor'
        exe_name = self.vrl_project_name
        actual_build_path = self.config.builds_path
        if self.cur_build_type == 'client':
            actual_build_path += '_client'
            windows_folder_name = 'WindowsClient'
            exe_name += 'Client'
        elif self.cur_build_type == 'server':
            actual_build_path += '_server'
            windows_folder_name = 'WindowsServer'
            exe_name += 'Server'

        exe_path = os.path.join(actual_build_path,
                                '{0}\\{1}\\Binaries\\Win64\\{2}.exe'.format(windows_folder_name,
                                                                            self.vrl_project_name,
                                                                            exe_name))
        exe_shortcut_path = os.path.join(actual_build_path,
                                         '{0}\\{1}.exe'.format(windows_folder_name, exe_name))

        # First extract the current version info resource from the executable
        cmd_args = ['-open', exe_path,
                    '-save', '.\\tmpversioninfo.rc',
                    '-action', 'extract',
                    '-mask', 'VERSIONINFO,,',
                    '-log', '.\\versionExtract.log']
        if launch(self.ResourceHackerPath, cmd_args) != 0:
            self.error = 'Failed to extract version info resource!!'
            return False

        # make sure there is enough version points or the resource editor gets angry...
        ver_str = self.config.version_str + '.0' * (4 - len(self.config.version_str.split('.')))

        # Next edit the resource with our changes
        cmd_args = ['-i', '.\\tmpversioninfo.rc',
                    '-o', '.\\tmpversioninfo.rc',
                    '-v', ver_str,
                    '-n', self.vrl_project_description,
                    '-c', self.vrl_company_name,
                    '-f', '{}.exe'.format(self.vrl_project_name),
                    '-a', self.vrl_project_fingerprint,
                    '-s', self.vrl_sdk_version]
        if launch(os.path.join(self.config.uproject_dir_path, self.ResourceEditorPath), cmd_args) != 0:
            self.error = 'Failed to edit version info resource!!'
            return False

        # Also update the product version strings from the unreal string
        with open('.\\tmpversioninfo.rc') as fp:
            file_contents = fp.read()
            re_exp = re.compile('.*PRODUCTVERSION\s+(.+)')
            re_exp2 = re.compile('\s*VALUE\s+"ProductVersion",\s+"(.*?)"')
            matches = re_exp.search(file_contents)
            matches2 = re_exp2.search(file_contents)
            if len(matches.groups()) != 1 or len(matches2.groups()) != 1:
                error_exit('Unable to find ProductVersion section in rc!!', not self.config.automated)
            new_contents = \
                file_contents[0:matches.start(1)] + \
                self.config.version_str.replace('.', ',') + \
                file_contents[matches.end(1):matches2.start(1)] + \
                self.config.version_str + \
                file_contents[matches2.end(1):]

        with open('.\\tmpversioninfo.rc', 'w') as fp:
            fp.write(new_contents)

        # Compile the rc
        with contextlib.suppress(FileNotFoundError):
            os.unlink('.\\tmpversioninfo.res')

        if launch(os.path.join(self.config.uproject_dir_path, self.ResourceCompilerPath),
                  ['.\\tmpversioninfo.rc']) != 0:
            self.error = 'Unable to compile resource!!'
            return False

        # Finally put the resource back into the executable
        cmd_args = ['-open', exe_path,
                    '-save', exe_path,
                    '-action', 'addoverwrite',
                    '-res', '.\\tmpversioninfo.res',
                    '-mask', 'VERSIONINFO,,',
                    '-log', 'versionOverwrite.log']
        if launch(os.path.join(self.config.uproject_dir_path, self.ResourceHackerPath), cmd_args) != 0:
            self.error = 'Unable to inject new version info resource into executable!!'
            return False

        cmd_args[1] = exe_shortcut_path
        cmd_args[3] = exe_shortcut_path
        if launch(os.path.join(self.config.uproject_dir_path, self.ResourceHackerPath), cmd_args) != 0:
            self.error = 'Unable to inject new version info resource into shortcut executable!!'
            return False

        return True
