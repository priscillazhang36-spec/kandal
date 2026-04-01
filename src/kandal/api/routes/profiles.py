from uuid import UUID

from fastapi import APIRouter, HTTPException

from kandal.core.supabase import get_supabase
from kandal.schemas.preferences import PreferencesCreate, PreferencesResponse, PreferencesUpdate
from kandal.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate

router = APIRouter()


@router.post("/", response_model=ProfileResponse, status_code=201)
def create_profile(body: ProfileCreate):
    client = get_supabase()
    resp = client.table("profiles").insert(body.model_dump()).execute()
    return resp.data[0]


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: UUID):
    client = get_supabase()
    resp = client.table("profiles").select("*").eq("id", str(profile_id)).execute()
    if not resp.data:
        raise HTTPException(404, "Profile not found")
    return resp.data[0]


@router.patch("/{profile_id}", response_model=ProfileResponse)
def update_profile(profile_id: UUID, body: ProfileUpdate):
    client = get_supabase()
    data = body.model_dump(exclude_unset=True)
    resp = client.table("profiles").update(data).eq("id", str(profile_id)).execute()
    if not resp.data:
        raise HTTPException(404, "Profile not found")
    return resp.data[0]


@router.put("/{profile_id}/preferences", response_model=PreferencesResponse)
def upsert_preferences(profile_id: UUID, body: PreferencesCreate):
    client = get_supabase()
    data = body.model_dump()
    data["profile_id"] = str(profile_id)
    resp = client.table("preferences").upsert(data, on_conflict="profile_id").execute()
    return resp.data[0]


@router.get("/{profile_id}/preferences", response_model=PreferencesResponse)
def get_preferences(profile_id: UUID):
    client = get_supabase()
    resp = (
        client.table("preferences")
        .select("*")
        .eq("profile_id", str(profile_id))
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Preferences not found")
    return resp.data[0]


@router.patch("/{profile_id}/preferences", response_model=PreferencesResponse)
def update_preferences(profile_id: UUID, body: PreferencesUpdate):
    client = get_supabase()
    data = body.model_dump(exclude_unset=True)
    resp = (
        client.table("preferences")
        .update(data)
        .eq("profile_id", str(profile_id))
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Preferences not found")
    return resp.data[0]
