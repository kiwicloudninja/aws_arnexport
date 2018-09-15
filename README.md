# arnexport

> Creates an AWS CloudFormation template in YAML format from an AWS resource ARN.

This script will create a CloudFormation template that should pass aws cloudformation validation but;
The template itself may not be usable without some tweaking. For example, Lambda functions export with
a code property that can't be used by CloudFormation as is. The script in it's current state does
produce a fairly useable template suitable for editing.

## Table of Contents

- [Install](#install)
- [Usage](#usage)
- [Contribute](#contribute)
- [License](#license)

## Install
```
virtualenv -p python3 arnexport
pip install pyyaml
pip install boto3
```
Obtain the latest us-east-1 CloudFormationResourceSpecification.json file from:
https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-resource-specification.html

## Usage
```
arnexport.py <profile_name> <aws_arn>
```
<profile_name> is a valid profile in your .aws config file
<aws_arn> is the arn for an existing resource in your aws account

EG:
```
./arnexport.py myprofile arn:aws:lambda:us-west-2:012345678:function:mycoolfunc
```

## Contribute

PRs accepted.

## License

Apache 2.0 © 2018 Shane Davis
