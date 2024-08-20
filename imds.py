import boto3
import click
import jmespath
from datetime import datetime, timedelta
from dateutil.tz import tzutc
import pandas as pd
from tabulate import tabulate

session = boto3.Session()


def create_client(session,*args,**kwargs):
    for  region in args:
        ec2_client = session.client('ec2',region_name = region)
        return(ec2_client)
    
    if kwargs['region']:
        cw_client = session.client('cloudwatch',region_name = kwargs['region'])
        return(cw_client)

def list_regions(session):
    default_client = session.client('ec2')
    response = default_client.describe_regions()
    regions = jmespath.search('Regions[*].RegionName', response)
    return(regions)

def describe_instances(session,region_list,*args,**kwargs):
    r_dict = {}
    outside_list = [] 
    if region_list and not args:
        
        
        for region in region_list:
            
            datalist = []
            
            client = create_client(session,region)
            
            try:
                paginator = client.get_paginator('describe_instances')
                page_iterator = paginator.paginate()
                filtered_iterator = page_iterator.search("Reservations[].Instances[?State.Name =='running'].{InstanceId: InstanceId,httptokens : MetadataOptions.HttpTokens,LaunchTime:LaunchTime}")
                
                data = next(filtered_iterator)
                if data:
                    
                    datalist.append(data[0])
                    r_dict = {region:datalist}
                    outside_list.append(r_dict)

                    

                 
                for data in filtered_iterator:
                    if(data):
                        datalist.append(data[0])
                        
                    
                        
            except:
                pass
            
            

     
    else:
        
        for region in region_list:
            datalist = []
            for instance_id in args[0]:
            
                client = create_client(session,region)
                query = (
    f"Reservations[].Instances[?State.Name=='running' && InstanceId=='{instance_id}']."
    f"{{InstanceId: InstanceId, httptokens: MetadataOptions.HttpTokens,LaunchTime:LaunchTime}}"
)
                try:
                    paginator = client.get_paginator('describe_instances')
                    page_iterator = paginator.paginate()
                    filtered_iterator = page_iterator.search(query)
                
                    data = next(filtered_iterator)
                    if data:
                        datalist.append(data[0])
                        r_dict = {region:datalist}
                        outside_list.append(r_dict)

                    for data in filtered_iterator:
                        if(data):
                            datalist.append(data[0])
                    
                except:
                    pass

    return(outside_list)
    

def  cloudwatch_metrics(session,compiled_list,dur,metricname,*args,**kwargs):
    
    if dur > 63:
        period = 2592000
    elif dur > 15 and dur < 63:
        period = 86400
    else:
        period = 3600
    
# Get the current date and time
    current_datetime = datetime.now()
    end_time = current_datetime.isoformat()

# Calculate the past date and time
    past_datetime = current_datetime - timedelta(days=dur)
    start_time = past_datetime.isoformat()
    data_list = []
    comment = ""
    metadatanotoken_sum = 0
    metadatanotokenrejected_sum = 0

    for out_lists in compiled_list:
        for key,value in out_lists.items():
            region = key
            cloudwatch_client = create_client(session,region = region)
            for values in value:
                instance_id = values['InstanceId']
                httptokens = values['httptokens']
                launch_date = values['LaunchTime'].date()
                if metricname:
                    headers = ["instanceid","region","http-tokens",metricname,"duration in days","launch_date"]
                    response = cloudwatch_client.get_metric_statistics(Namespace='AWS/EC2',MetricName= metricname, Dimensions=[
                    {
                    'Name': 'InstanceId',
                    'Value': instance_id },
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=[
                    'Sum',
                    ],
                    )
                    

                    datapoints = jmespath.search('Datapoints[*].Sum', response)
                    total_sum = (sum(datapoints))
                    
                    info = [instance_id,region,httptokens,int(total_sum),dur,launch_date]
                    data_list.append(info)
                    
 
                else:
                    headers = ["instanceid","region","http-tokens","MetadataNoToken","MetadataNoTokenRejected","duration in days","launch_date","Comments"]
                    metricnamelist = ['MetadataNoToken', 'MetadataNoTokenRejected']
                    for metric_name in metricnamelist:
                        response = cloudwatch_client.get_metric_statistics(Namespace='AWS/EC2',MetricName= metric_name, Dimensions=[
                        {
                        'Name': 'InstanceId',
                        'Value': instance_id },
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=[
                        'Sum',
                        ],
                        )
                        datapoints = jmespath.search('Datapoints[*].Sum', response)
                        total_sum = (sum(datapoints))
                        
                        if metric_name == "MetadataNoToken":
                            metadatanotoken_sum = total_sum
                        else:
                            metadatanotokenrejected_sum = total_sum

                        if metadatanotoken_sum == 0 and metadatanotokenrejected_sum == 0:
                            comment = "No attempt to use IMDSv1"
                        else:
                            comment = "-"

                    info = [instance_id,region,httptokens,int(metadatanotoken_sum),int(metadatanotokenrejected_sum),dur,launch_date,comment]
                    data_list.append(info)
                    

    
    
    table = tabulate(data_list, headers = headers)
    print(table)
    

     



        


@click.option('profilename','-profile', nargs = 1)
@click.group()
@click.pass_context
def main(ctx,profilename):
    
    if profilename:
        session = boto3.Session(profile_name = profilename)
    else:
        session = boto3.Session()

    ctx.obj = session



@main.command()
@click.option('region','--region',nargs = 1,default = 'All',help = "aws region")
@click.option('instanceid','-id',multiple = True,help = "instance id")
@click.option('--metricname','--metric',type=click.Choice(['MetadataNoToken', 'MetadataNoTokenRejected'], case_sensitive=False),help = "Choose the metric name .If not specified both metrics returned")
@click.option('duration','--dur', required = True,type=click.IntRange(1, 456, clamp=True),help = "duration of metrics in days")
@click.pass_context
def getmetrics(ctx,region,instanceid,duration,metricname):
    '''cmd to get imds calls metric data
      usage: imds.py -profile getmetrics  region(optional),instance_id(optional),duration(required in number of days and maxes out at 456 days ie 15 months)'''
    session = ctx.obj
    
    if region == 'All' and not(instanceid):
        region_list = list_regions(session)
        
        compiled_list = describe_instances(session,region_list)

    elif region != 'All' and not(instanceid):

        region_list = [region]
        compiled_list = describe_instances(session,region_list)
        
    elif region != 'All' and instanceid:
        region_list = [region]
        
        compiled_list = describe_instances(session,region_list,instanceid)
    
    

    cloudwatch_metrics(session,compiled_list,duration,metricname)


    

    
    #print(data,region_name)
    


@main.command()
@click.pass_context
def V1toV2(ctx):
    pass

@main.command()
@click.pass_context
def V2toV1(ctx):
    print(ctx.obj)
    pass

if __name__ == "__main__":
    main()