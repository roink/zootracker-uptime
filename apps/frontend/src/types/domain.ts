export interface ZooSummary {
  id: string;
  name: string;
  slug?: string;
  city?: string | null;
  latitude: number;
  longitude: number;
  is_favorite?: boolean;
}

export interface AnimalSummary {
  id: string;
  slug?: string;
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

export interface PopularAnimal extends AnimalSummary {
  zoo_count?: number | null;
  iucn_conservation_status?: string | null;
  default_image_url?: string | null;
}

export interface SiteSummary {
  species: number;
  zoos: number;
  countries: number;
  sightings: number;
}

export interface ZooAnimalTile extends AnimalSummary {
  scientific_name?: string | null;
  name_en?: string | null;
  name_de?: string | null;
  zoo_count?: number | null;
  default_image_url?: string | null;
  is_favorite?: boolean | null;
  seen?: boolean;
  klasse?: number | null;
  ordnung?: number | null;
  familie?: number | null;
}

export interface ZooAnimalFacetOption {
  id: number;
  name_de?: string | null;
  name_en?: string | null;
  count: number;
}

export interface ZooAnimalListing {
  items: ZooAnimalTile[];
  total: number;
  available_total: number;
  inventory: ZooAnimalTile[];
  facets: {
    classes: ZooAnimalFacetOption[];
    orders: ZooAnimalFacetOption[];
    families: ZooAnimalFacetOption[];
  };
}
