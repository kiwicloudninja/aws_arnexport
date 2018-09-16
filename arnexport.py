#!/usr/bin/env python
'''
 Author:: Shane Davis (<shane@kiwicloudninja.com>)

 Creates an AWS CloudFormation template in YAML format from an AWS resource ARN.

 Copyright 2018, Shane Davis

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
'''

from os import sys
import json
import boto3
import botocore
import yaml

class ARNExport():
    '''Creates an AWS CloudFormation template in YAML format from an AWS resource ARN.'''

    def __init__(self, profile, arn_str):
        self.func_type = 0
        self.profile_name = profile
        self.arn_str = arn_str
        self.arn_map = self.get_arn_map(arn_str)
        self.cf_resources = {}
        self.raw = {}

    @classmethod
    def get_cloudform_spec(cls):
        '''returns a CloudFormation dict from the AWS Specification json '''
        with open("CloudFormationResourceSpecification.json", 'r') as json_file:
            jsonspec = json.load(json_file)

        return jsonspec


    def get_dict_value(self, search_key, search_dict):
        '''crawls through dict to find key in dict'''
        found_value = None
        for key, value in search_dict.items():
            found_value = value if key == search_key else None
            if found_value is None and isinstance(value, dict):
                found_value = self.get_dict_value(search_key, value)
            if found_value is not None:
                break

        return found_value


    def expand_arn(self, arn_str):
        '''Returns a CloudFormation !Ref string to a nested ARN resource'''
        print('Extracting {}'.format(arn_str))
        cf_resource = self.format_resource(self.get_resource_from_arn(arn_str), arn_str)
        self.cf_resources.update(cf_resource['resource'])

        return "!Ref {}".format(cf_resource['name'])


    def get_resource_type(self, arn_map):
        '''returns a CloudFormation resource type from incorrectly cased boto3 resource type'''
        api_type = "AWS::{}::{}".format(arn_map['service'], arn_map['resourcetype'])
        cloudform_spec = self.get_cloudform_spec()
        for key in cloudform_spec['ResourceTypes'].keys():
            if key.lower() == api_type.lower():
                resource_properties = cloudform_spec['ResourceTypes'][key]['Properties']
                return {'Type':key, 'Properties': resource_properties}

        return None


    def get_resource_name(self, arn_map):
        '''Extracts a readable name from the ARN map'''
        name = arn_map['resource']
        if 'qualifier' in arn_map and self.func_type == 0:
            name = arn_map['qualifier']

        return name.replace('-', '')


    def format_resource(self, resource, arn_str=''):
        '''Formats boto3 client resource into a CloudFormation resource'''
        arn_map = self.get_arn_map(arn_str) if arn_str != '' else self.arn_map

        resource_type = self.get_resource_type(arn_map)
        if resource_type is None:
            return None

        resource_name = self.get_resource_name(arn_map)
        cf_resource = {
            resource_name: {
                'Type': resource_type['Type'],
                'Properties': {}
            }
        }

        for key in resource_type['Properties'].keys():
            value = self.get_dict_value(key, resource)
            if value is None:
                continue

            if isinstance(value, str) and value.find('arn:aws') >= 0:
                cf_resource[resource_name]['Properties'][key] = self.expand_arn(value)
                continue

            cf_resource[resource_name]['Properties'][key] = value

        return {'name': resource_name, 'resource': cf_resource}


    def get_aws_client(self, arn_map=''):
        '''returns an aws client for the resource to be queried'''
        arn_map = self.arn_map if arn_map == '' else arn_map
        region = 'us-east-1' if arn_map['region'] == '' else arn_map['region']
        session = boto3.Session(profile_name=self.profile_name, region_name=region)

        return session.client(arn_map['service'])


    def get_arn_map(self, arn_str=''):
        '''Returns an ARN mapped dict from an AWS ARN resource string'''
        arn_common = "arn:partition:service:region:account-id:"
        arn_resources = [
            "resource",
            "resourcetype:resource",
            "resourcetype:resource:qualifier",
            "resourcetype/resource",
            "resourcetype/resource:qualifier",
            "",
            "resourcetype/resource/qualifier"
        ]
        arn_str = self.arn_str if arn_str == '' else arn_str
        arn_type = (arn_str.count(':') - arn_common.count(':')) + (arn_str.count('/') * 3)
        arn_suffix = arn_resources[arn_type]
        arn_keys = "{}{}".format(arn_common, arn_suffix).replace('/', ':').split(":")
        arn_map = {}
        for ndx, value in enumerate(arn_str.replace('/', ':').split(":")):
            arn_map[arn_keys[ndx]] = value

        return arn_map

    @classmethod
    def get_resource_function(cls, client, pattern):
        '''tries to obtain the correct client function to query a resource'''
        try:
            func = getattr(client, pattern)
        except AttributeError:
            func = None
        return func


    def get_resource_from_arn(self, arn_str=''):
        '''returns a dict boto3 client resource from an arn_str'''
        arn_map = self.get_arn_map(arn_str) if arn_str != '' else self.arn_map
        aws = self.get_aws_client(arn_map)

        if 'resourcetype' not in arn_map:
            sys.exit(
                "I don't have a way of exporting this resource: {}{}".format(arn_str, self.arn_str)
            )

        func = self.get_resource_function(aws, 'get_{}'.format(arn_map['resourcetype']))
        if func is None:
            func = getattr(aws, 'describe_{}s'.format(arn_map['resourcetype']))
            self.func_type = 1
            if func is None:
                sys.exit("I don't have a way of exporting this resource")

        arg_name = '{}Name'.format(arn_map['resourcetype'].title())
        arg_key = self.get_resource_name(arn_map)
        args = {arg_name: arg_key}

        try:
            resource = func(**args)
        except botocore.exceptions.ParamValidationError:
            sys.exit("I don't have a way of retrieving this resource for export.")

        resource.pop('ResponseMetadata', None)

        self.raw.update(resource)

        return resource


    def write_yaml_template(self):
        '''Creates a yaml CloudFormation template from an AWS ARN'''
        print('Retrieving {}'.format(self.arn_str))
        cf_resource = self.format_resource(self.get_resource_from_arn())
        self.cf_resources.update(cf_resource['resource'])

        descr = "{}_{}_{}".format(
            cf_resource['name'],
            self.arn_map['service'],
            self.arn_map['resourcetype']
        )
        print('Writing {}.yml file'.format(descr))
        template = {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Description': 'Exported {} from {}'.format(descr, self.arn_str),
            'Resources': self.cf_resources
        }

        with open("templates/{}.yml".format(descr), 'w') as yaml_file:
            yaml.dump(template, yaml_file, default_flow_style=False)

        template = {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Description': 'Exported {} from {}'.format(descr, self.arn_str),
            'Resources': self.raw
        }

        with open("templates/{}_raw.yml".format(descr), 'w') as yaml_file:
            yaml.dump(template, yaml_file, default_flow_style=False)

if __name__ == "__main__":
    EXPORTER = ARNExport(sys.argv[1], sys.argv[2])
    EXPORTER.write_yaml_template()
