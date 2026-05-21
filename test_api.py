from gradio_client import Client, handle_file
import urllib.request
import traceback

client = Client('http://127.0.0.1:42000')

try:
    print('Extracting GLB...')
    res = client.predict(
        state_path='/home/drake/.pinokio-pixal3d/app/tmp/state_1779337434307_3548.npz',
        decimation_target=100000,
        texture_size=1024,
        session_id='test',
        api_name='/extract_glb_api'
    )
    print(res)
except Exception as e:
    traceback.print_exc()
