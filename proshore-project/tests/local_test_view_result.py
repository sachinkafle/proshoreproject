from azure.storage.blob import BlobServiceClient

# Connect to the local Azurite emulator
conn_str = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
blob_service_client = BlobServiceClient.from_connection_string(conn_str)
container_client = blob_service_client.get_container_client("processed-tickets")

print("Fetching results from the 'processed-tickets' Azure Blob container...\n")

# List all files and print their contents
blobs_found = False
for blob in container_client.list_blobs():
    blobs_found = True
    print(f"--- 📄 Result Document: {blob.name} ---\n")
    blob_client = container_client.get_blob_client(blob.name)
    
    # Download the JSON string from Azure Storage and print it
    data = blob_client.download_blob().readall().decode('utf-8')
    print(data)
    print("\n----------------------------------------\n")

if not blobs_found:
    print("No processed tickets found yet. Remember to run local_test_upload.py first!")
