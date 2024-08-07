from fastapi import Request, HTTPException, APIRouter, Response, Query
from typing import List

router = APIRouter()


@router.get("/list-phrase")
def get_rate(request: Request,
             limit: int = 20,
             offset: int = 0):
    clip_server = request.app.clip_server

    phrase_list = clip_server.get_phrase_list(offset, limit)

    return phrase_list

@router.get("/clip-vector")
def get_clip_vector(request: Request,
             phrase : str):
    clip_server = request.app.clip_server

    clip_vector = clip_server.get_clip_vector(phrase)

    return clip_vector

@router.get("/clip-vector-from-image-path")
def clip_vector_from_image_path(request: Request,
                                image_path : str,
                                bucket: str = "datasets"):
    clip_server = request.app.clip_server

    clip_vector = clip_server.get_image_clip_from_minio(image_path, bucket)

    return clip_vector


@router.get("/cosine-similarity")
def clip_vector_from_image_path(request: Request,                 
             image_path : str,
             phrase : str,
             bucket: str = "datasets"):
    clip_server = request.app.clip_server

    similarity = clip_server.compute_cosine_match_value(phrase, bucket, image_path)

    return similarity

@router.post("/cosine-similarity-list")
def clip_vector_from_image_path(request: Request,
                                image_path : List[str],
                                phrase : str,
                                bucket: str = "datasets"):
    clip_server = request.app.clip_server

    similarity_list = clip_server.compute_cosine_match_value_list(phrase, bucket, image_path)

    return {
        "similarity_list" : similarity_list
    }

@router.get("/image-clip")
def clip_vector_from_image_path(request: Request,
             image_path : str,
             bucket: str = "datasets"):
    clip_server = request.app.clip_server

    image_clip_vector_numpy = clip_server.get_image_clip_from_minio(image_path, bucket)

    return image_clip_vector_numpy

@router.put("/add-phrase")
def add_job(request: Request, phrase : str):
    clip_server = request.app.clip_server

    clip_server.add_phrase(phrase)

    return True

@router.get("/kandinsky-clip-vector")
def get_kandinsky_clip_vector(request: Request,
             image_path : str):
    clip_server = request.app.clip_server

    clip_vector = clip_server.compute_kandinsky_image_clip_vector(image_path)

    return clip_vector

