import azure.functions as func
import logging
import json

from handlers import TicketActionHandler

app = func.FunctionApp()

# Instantiate the dependency-injected action handler globally
# This ensures it survives across multiple identical function triggers.
action_handler = TicketActionHandler()

@app.function_name(name="TicketCategorizer")
@app.blob_trigger(arg_name="myblob", path="incoming-tickets/{name}", connection="AzureWebJobsStorage")
@app.blob_output(arg_name="outputblob", path="processed-tickets/{name}.json", connection="AzureWebJobsStorage")
async def process_ticket(myblob: func.InputStream, outputblob: func.Out[str]):
    """
    Very skinny entrypoint. Its only job is to accept the Azure Trigger
    and immediately delegate all business logic to the Action Handler.
    """
    logging.info(f"Trigger fired for blob: {myblob.name}")
    
    try:
        content = myblob.read().decode('utf-8')
        
        # Delegate routing and extraction to the handler
        final_result = await action_handler.handle_ticket(content, myblob.name)
        
        outputblob.set(json.dumps(final_result, indent=4))
        logging.info(f"Pipeline completed for: {myblob.name}")
        
    except Exception as e:
        # Note: True Dead Letter Quarantining would happen here
        logging.error(f"Execution failed for {myblob.name}. Moving to DLQ. Error: {str(e)}")
        raise e
