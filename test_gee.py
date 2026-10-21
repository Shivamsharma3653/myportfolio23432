import ee

PROJECT_ID = "project-43e60592-2ef1-4cf2-bb4"

ee.Authenticate()
ee.Initialize(project=PROJECT_ID)

print(ee.String("Hello from Earth Engine").getInfo())