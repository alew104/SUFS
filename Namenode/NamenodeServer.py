"""
NamenodeServer.py
"""
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

PORT = 8000
HOST = "localhost"


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


# Create server
server = SimpleXMLRPCServer((HOST, PORT), requestHandler=RequestHandler)
server.register_introspection_functions()


# Register a function under a different name
def hello_world():
    return "Hello, Namenode!\n"


# Register hello world function
server.register_function(hello_world)

# Run the server's main loop
print("Staring Namenode Server on port " + str(PORT) + "...")
server.serve_forever()