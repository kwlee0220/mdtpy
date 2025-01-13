def twin_id:
	.id;

def filter_by_id(id):
	select(.id == id);
def filter_not_by_id(id):
	select(.id != id);

def filter_by_status(status):
	select(.status == status);
def filter_not_by_status(status):
	select(.status != status);

def summarize:
	{
		"id": .id,
		"status": .status,
		"assetType": .assetType,
		"baseEndpoint": .baseEndpoint,
		"parameters": .parameters,
		"operations": .operations
	};

def to_csv:
	.parameters[] | .name