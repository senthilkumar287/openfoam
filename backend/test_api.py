from app import app

client = app.test_client()

resp = client.get('/')
print('root', resp.status_code, resp.json)
resp = client.post('/api/mesh/create', json={'nx':10,'ny':10,'nz':1,'domain':[1,1,1]})
print('/api/mesh/create', resp.status_code, resp.json)
resp = client.post('/api/solver/create', json={'type':'laplacianFoam','config':{'alpha':0.1}})
print('/api/solver/create', resp.status_code, resp.json)
resp = client.post('/api/bc/set', json={'patch':'wall','type':'dirichlet','value':100})
print('/api/bc/set', resp.status_code, resp.json)
resp = client.post('/api/simulate/run', json={'max_iters':5,'dt':0.01})
print('/api/simulate/run', resp.status_code, resp.json)
resp = client.get('/api/results/heatmap')
print('/api/results/heatmap', resp.status_code, resp.json)
