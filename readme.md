The script is helpful in transitioning IMDSv1 instances in aws to IMDSV2.
It uses click for command line creation and tabulate to output metrics in table format.

Please install tabulate before you run the script.
pip install tabulate


Usage examples 


python imds.py --help                                                     
Usage: imds.py [OPTIONS] COMMAND [ARGS]...

Options:
  --profile TEXT  profile to use for the operation from aws config file on disk.
  --help          Show this message and exit.

Commands:
  getmetrics  cmd to get imds calls metric data usage: imds.py -profile...
  v1tov2      command to modify instances from IMDSv1 to IMDSv2
  v2tov1      command to modify instances from IMDSv2 to IMDSv1