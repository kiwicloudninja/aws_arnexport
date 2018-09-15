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
import yaml


def get_cloudform_spec():
    '''returns a CloudFormation dict from the AWS Specification json '''
    with open("CloudFormationResourceSpecification.json", 'r') as json_file:
        jsonspec = json.load(json_file)

    return jsonspec


def get_resource_type(api_type):
    '''returns a CloudFormation resource type from incorrectly cased boto3 resource type'''
    cloudform_spec = get_cloudform_spec()
    for key in cloudform_spec['ResourceTypes'].keys():
        if key.lower() == api_type.lower():
            return key
    return None


def get_dict_value(search_key, search_dict):
    '''crawls through dict to find key in dict'''
    found_value = None
    for key, value in search_dict.items():
        found_value = value if key == search_key else None
        if found_value is None and isinstance(value, dict):
            found_value = get_dict_value(search_key, value)
        if found_value is not None:
            break

    return found_value


def expand_arn(arn_str):
    '''Returns a CloudFormation !Ref string to a nested ARN resource'''
    print('Extracting {}'.format(arn_str))
    cf_resource = format_resource(get_resource_from_arn(arn_str), arn_str)
    cf_resources.update(cf_resource['resource'])

    return "!Ref {}".format(cf_resource['name'])


def format_resource(resource, arn_str=''):
    '''Formats boto3 client resource into a CloudFormation resource'''
    arn_map = get_arn_map(arn_str) if arn_str != '' else ARN_MAP
    resource_str = "AWS::{}::{}".format(arn_map['service'], arn_map['resourcetype'])
    resource_type = None

    cloudform_spec = get_cloudform_spec()
    for key in cloudform_spec['ResourceTypes'].keys():
        if key.lower() == resource_str.lower():
            resource_type = key

    if resource_type is None:
        return None

    resource_name = arn_map['qualifier'] if 'qualifier' in arn_map else arn_map['resource']
    resource_name = resource_name.replace('-', '')

    cf_resource = {
        resource_name: {
            'Type': resource_type,
            'Properties': {}
        }
    }

    resource_properties = cloudform_spec['ResourceTypes'][resource_type]['Properties']
    for key in resource_properties.keys():
        value = get_dict_value(key, resource)
        if value is None:
            continue

        if isinstance(value, str) and value.find('arn:aws') >= 0:
            cf_resource[resource_name]['Properties'][key] = expand_arn(value)
            continue

        cf_resource[resource_name]['Properties'][key] = value

    return {'name': resource_name, 'resource': cf_resource}


def get_aws_client(arn_map=''):
    '''returns an aws client for the resource to be queried'''
    arn_map = ARN_MAP if arn_map == '' else arn_map
    region = 'us-east-1' if arn_map['region'] == '' else arn_map['region']
    session = boto3.Session(profile_name=AWS_PROFILE_NAME, region_name=region)

    return session.client(arn_map['service'])


def get_arn_map(arn_str=''):
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
    arn_str = ARN_STR if arn_str == '' else arn_str
    arn_type = (arn_str.count(':') - arn_common.count(':')) + (arn_str.count('/') * 3)
    arn_suffix = arn_resources[arn_type]
    arn_keys = "{}{}".format(arn_common, arn_suffix).replace('/', ':').split(":")
    arn_map = {}
    for ndx, value in enumerate(arn_str.replace('/', ':').split(":")):
        arn_map[arn_keys[ndx]] = value

    return arn_map


def get_resource_from_arn(arn_str=''):
    '''returns a dict boto3 client resource from an ARN_STR'''
    arn_map = get_arn_map(arn_str) if arn_str != '' else ARN_MAP
    aws = get_aws_client(arn_map)
    func = getattr(aws, 'get_{}'.format(arn_map['resourcetype']))

    arg_name = '{}Name'.format(arn_map['resourcetype'].title())
    arg_key = arn_map['qualifier'] if 'qualifier' in arn_map else arn_map['resource']
    args = {arg_name: arg_key}

    resource = func(**args)
    resource.pop('ResponseMetadata', None)

    return resource


def write_yaml_template():
    '''Creates a yaml CloudFormation template from an AWS ARN'''
    print('Retrieving {}'.format(ARN_STR))
    cf_resource = format_resource(get_resource_from_arn())
    cf_resources.update(cf_resource['resource'])

    descr = "{}_{}_{}".format(cf_resource['name'], ARN_MAP['service'], ARN_MAP['resourcetype'])
    print('Writing {}.yml file'.format(descr))
    template = {
        'AWSTemplateFormatVersion': '2010-09-09',
        'Description': 'Exported {} from {}'.format(descr, ARN_STR),
        'Resources': cf_resources
    }

    with open("templates/{}.yml".format(descr), 'w') as yaml_file:
        yaml.dump(template, yaml_file, default_flow_style=False)

if __name__ == "__main__":
    AWS_PROFILE_NAME = sys.argv[1]
    ARN_STR = sys.argv[2]
    ARN_MAP = get_arn_map(ARN_STR)
    cf_resources = {}  # pylint: disable=C0103
    write_yaml_template()
