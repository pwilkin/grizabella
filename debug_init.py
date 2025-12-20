from grizabella.api.client import Grizabella
import inspect

print(f"File: {inspect.getfile(Grizabella)}")
print(f"Init args: {inspect.signature(Grizabella.__init__)}")

try:
    gb = Grizabella(db_name_or_path="test", use_gpu=True)
    print("Success!")
except TypeError as e:
    print(f"Error: {e}")
