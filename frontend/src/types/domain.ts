export interface ZooSummary {
  id: string;
  name: string;
  slug?: string;
  latitude: number;
  longitude: number;
  is_favorite?: boolean;
}

export interface AnimalSummary {
  id: string;
  slug: string;
  name_en?: string | null;
  name_de?: string | null;
  scientific_name?: string | null;
}

export interface Sighting {
  id: string;
  zoo_id: string;
  animal_id: string;
  sighting_datetime: string;
  created_at?: string;
  notes?: string | null;
  animal_name_en?: string | null;
  animal_name_de?: string | null;
  zoo_name?: string | null;
}

export interface Visit {
  id: string;
  zoo_id: string;
  visited_at: string;
  notes?: string | null;
}

export interface AuthUser {
  id?: string;
  email?: string | null;
  emailVerified?: boolean;
  [key: string]: unknown;
}

export interface VerificationRequestResult {
  response: Response;
  detail?: string;
}

export interface SearchResults {
  zoos: ZooSummary[];
  animals: AnimalSummary[];
}
