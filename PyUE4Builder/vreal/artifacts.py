#!/usr/bin/env python

import os
import json
from actions.action import Action
from utility.downloaders import download_file
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

__author__ = "Ryan Sheffer"
__copyright__ = "Copyright 2018, Ryan Sheffer Open Source"
__credits__ = ["Ryan Sheffer", "VREAL"]


class Artifacts(Action):
    """
    Pulls Artifacts from jenkins
    Meta: [last_client_app_build_num]
    """
    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.jenkins_client_app_url = kwargs['jenkins_client_app_url'] if 'jenkins_client_app_url' in kwargs else ''
        self.jenkins_client_app_meta_url = \
            kwargs['jenkins_client_app_meta_url'] if 'jenkins_client_app_meta_url' in kwargs \
            else 'api/python?pretty=true'
        self.artifacts_pull_list = kwargs['artifacts_pull_list'] if 'artifacts_pull_list' in kwargs else []
        self.build_num = 0
        build_meta = kwargs['build_meta'] if 'build_meta' in kwargs else None
        if build_meta is not None and getattr(build_meta, 'last_client_app_build_num', None) is not None:
            self.build_num = build_meta.last_client_app_build_num

    @staticmethod
    def get_arg_docs():
        return {
            'jenkins_client_app_url': 'URL to the Jenkins Job to pull artifacts from',
            'jenkins_client_app_meta_url': 'The API call to get the json for parsing. Defaulted to pretty python.',
            'artifacts_pull_list': 'List of dicts containing a directory too element '
                                   'and list of relative path artifacts'
        }

    def verify(self):
        if self.jenkins_client_app_url == '':
            return 'Jenkins Job URL is invalid!'
        return ''

    def run(self):
        from utility.common import print_action_info
        try:
            url_open = urlopen(self.jenkins_client_app_url + self.jenkins_client_app_meta_url)
            data_str = bytes.decode(url_open.read())
            for old, new in {'None': 'null', 'True': 'true', 'False': 'false'}.items():
                data_str = data_str.replace(old, new)
            jenkins_job_meta = json.loads(data_str)
            new_build_num = jenkins_job_meta['lastSuccessfulBuild']['number']
            if new_build_num != self.build_num:
                # pull the latest client application
                artifacts_url = jenkins_job_meta['lastSuccessfulBuild']['url']
                for artifacts_item in self.artifacts_pull_list:
                    for artifact_name in artifacts_item['artifacts']:
                        download_file(artifacts_url + 'artifact/' + artifact_name,
                                      os.path.join(self.config.uproject_dir_path, artifacts_item['dir_to']))
                print_action_info('Client Application Binaries updated to build {}!'.format(new_build_num))
                self.build_num = new_build_num
            else:
                print_action_info('Client Application Binaries up-to-date!')
        except HTTPError:
            self.error = 'Could not connect to jenkins. Are you connected to the VPN?'
            return False
        except URLError:
            self.error = 'URL error trying to connect to jenkins!'
            return False
        return True
