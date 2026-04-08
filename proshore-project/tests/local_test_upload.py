import os
import sys
from azure.storage.blob import BlobServiceClient

# Standard Azurite Local Connection String
conn_str = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"

try:
    print("Connecting to Azurite...")
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    
    # 1. Calculate path to sample tickets relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    tickets_dir = os.path.join(project_root, "sample_tickets")

    # 2. Parse command line arguments
    # Usage: python tests/local_test_upload.py ticket-001.txt
    if len(sys.argv) > 1:
        target_files = sys.argv[1:]
    else:
        # If no args, upload all .txt files in the directory
        target_files = [f for f in os.listdir(tickets_dir) if f.endswith(".txt")]
        print("💡 No specific ticket provided. Uploading everything...")

    # 3. Create containers if they don't exist
    for container_name in ["incoming-tickets", "processed-tickets"]:
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()

    # 4. Upload indicated files
    files_uploaded = 0
    for filename in target_files:
        file_path = os.path.join(tickets_dir, filename)
        
        if not os.path.exists(file_path):
            print(f"❌ Error: File not found at {file_path}")
            continue

        blob_client = blob_service_client.get_blob_client(container="incoming-tickets", blob=filename)
        
        print(f"📤 Uploading {filename}...")
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        files_uploaded += 1
            
    if files_uploaded > 0:
        print(f"\n✅ Successfully uploaded {files_uploaded} tickets!")
    else:
        print("\n⚠️ No tickets were uploaded.")
    
except Exception as e:
    print(f"❌ Error: {e}")
