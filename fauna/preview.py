"""Separate localhost read-only wildlife preview; never starts human AI inference."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
from caitanya.engine import World
from .ecology import Ecosystem

def create_preview():
    world=World(width=96,depth=96);eco=Ecosystem(world)
    published=eco.public()
    terrain_data=dict(width=world.width,depth=world.depth,terrain=[dict(x=x,z=z,size=1,
         biome=world.terrain_at(x,z)['biome']) for x in range(world.width) for z in range(world.depth)])
    async def worker():
        nonlocal published
        while True:
            await asyncio.sleep(.8);eco.step(world);published=eco.public()
    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(worker())
        try:yield
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    app=FastAPI(lifespan=lifespan)
    @app.get('/api/wildlife')
    def wildlife():return published
    @app.get('/api/terrain')
    def terrain():return terrain_data
    app.mount('/',StaticFiles(directory=Path(__file__).resolve().parent/'web',html=True))
    return app

if __name__=='__main__':uvicorn.run(create_preview(),host='127.0.0.1',port=8011)
