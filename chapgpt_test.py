from mdtpy import connect

# Connect to the MDT server
mdt = connect()

# Server URL for the operation
operation_server = "http://localhost:12987"  # Replace with the actual server URL

try:
    # Access the 'test' Twin and the 'Simulation' operation
    test_twin = mdt.instances['test']
    simulation_op = test_twin.operations['Simulation']

    # Set the input value for 'IncAmount'
    simulation_op.inputs['IncAmount'] = -30  # Update the input value

    # Execute the Simulation operation
    result = simulation_op(
        out_Data=test_twin.parameters('Data'),  # Store output 'Data' in the 'Data' parameter
        server=operation_server  # Specify the operation server
    )

    print("Simulation operation executed successfully.")
    print(f"Result: {result}")

except KeyError as e:
    print(f"KeyError: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
