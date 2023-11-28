import os
import boto3
import email
import re
from email.utils import parseaddr
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

region = os.environ['Region']

def get_message_from_s3(message_id):

    incoming_email_bucket = os.environ['MailS3Bucket']
    incoming_email_prefix = os.environ['MailS3Prefix']

    if incoming_email_prefix:
        object_path = (incoming_email_prefix + "/" + message_id)
    else:
        object_path = message_id

    object_http_path = (f"http://s3.console.aws.amazon.com/s3/object/{incoming_email_bucket}/{object_path}?region={region}")

    # Create a new S3 client.
    client_s3 = boto3.client("s3")

    # Get the email object from the S3 bucket.
    object_s3 = client_s3.get_object(Bucket=incoming_email_bucket,
        Key=object_path)
    # Read the content of the message.
    file = object_s3['Body'].read()

    file_dict = {
        "file": file,
        "path": object_http_path
    }
    # print(file_dict)
    return file_dict

def create_message(file_dict):

    sender = os.environ['MailSender']
    recipient = os.environ['MailRecipient']

    separator = ";"

    # Parse the email body.
    mailobject = email.message_from_string(file_dict['file'].decode('utf-8'))
    
    
    # Include sender's email address in the message dictionary
    sender_email = mailobject.get_all('From')
    # Find the start and end indexes of the email address
    sender_email_filtered = parseaddr(sender_email[0])[1]
    print(type(sender_email_filtered))
    
    # Create a new subject line.
    subject_original = mailobject['Subject']
    subject = subject_original
    
    # Extract the HTML part of the email body
    html_part = None
    for part in mailobject.walk():
        if part.get_content_type() == 'text/html':
            html_part = part.get_payload(decode=True).decode('utf-8')
            break

    # The body text of the email.
    body_text = (f"<div>email from {sender_email_filtered}</div><br> " + html_part) if html_part else mailobject.get_payload()
    print(body_text)

    # The file name to use for the attached message. Uses regex to remove all
    # non-alphanumeric characters, and appends a file extension.
    filename = re.sub('[^0-9a-zA-Z]+', '_', subject_original) + ".eml"

    # Create a MIME container.
    msg = MIMEMultipart()
    # Create a MIME text part.
    text_part = MIMEText(body_text, _subtype="html")
    # Attach the text part to the MIME message.
    msg.attach(text_part)
    
    
    
    

    # Add subject, from and to lines.
    msg['Subject'] = subject
    msg['From'] = sender
    #receiving Permissions are not granted and is blocking, even I am in Production: 
    #msg['From'] = sender_email_filtered
    msg['To'] = recipient

    # Create a new MIME object.
    att = MIMEApplication(file_dict["file"], filename)
    att.add_header("Content-Disposition", 'attachment', filename=filename)

    # Attach the file object to the message.
    msg.attach(att)
    
    # Include sender's email address in the message dictionary
    print(f"Sender's Email: {sender_email}")
    print(f"Original config's Email: {sender}")
    

    message = {
        "Source": sender,
        "Destinations": recipient,
        "Data": msg.as_string(),
        "Sender": sender_email_filtered
    }

    return message


def send_email(message):
    aws_region = os.environ['Region']

# Create a new SES client.
    client_ses = boto3.client('ses', region)

    # Send the email.
    try:
        #Provide the contents of the email.
        response = client_ses.send_raw_email(
            Source=message['Source'],
            #Source=message['Sender'],
            Destinations=[
                message['Destinations']
            ],
            RawMessage={
                'Data':message['Data']
            }
        )

    # Display an error if something goes wrong.
    except ClientError as e:
        output = e.response['Error']['Message']
    else:
        output = "Email sent! Message ID: " + response['MessageId']

    return output

def lambda_handler(event, context):
    # Get the unique ID of the message. This corresponds to the name of the file
    # in S3.
    message_id = event['Records'][0]['ses']['mail']['messageId']
    print(f"Received message ID {message_id}")

    # Retrieve the file from the S3 bucket.
    file_dict = get_message_from_s3(message_id)

    # Create the message.
    message = create_message(file_dict)

    # Send the email and print the result.
    result = send_email(message)
    print(result)