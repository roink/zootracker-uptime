import { useState, useEffect, useCallback, useId, useRef } from 'react';
import type { ChangeEvent, FormEvent, KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';

import { API } from '../api';
import { useAuth } from '../auth/AuthContext';
import useAuthFetch from '../hooks/useAuthFetch';
import useSearchSuggestions from '../hooks/useSearchSuggestions';
import type { AnimalSummary, ZooSummary, Sighting } from '../types/domain';
import { getZooDisplayName } from '../utils/zooDisplayName';

export type AnimalOption = AnimalSummary & { slug?: string | null };

export type ZooOption = ZooSummary & {
  slug?: string | null;
  name_en?: string | null;
  name_de?: string | null;
};

interface LogSightingProps {
  animals?: AnimalOption[] | null;
  zoos?: ZooOption[] | null;
  defaultAnimalId?: string;
  defaultZooId?: string;
  defaultDate?: string | null;
  initialAnimalName?: string;
  initialZooName?: string;
  defaultNotes?: string;
  sightingId?: string | null;
  titleId?: string;
  onLogged?: () => void;
  onCancel?: () => void;
  onDeleted?: () => void;
}


// Reusable forms for logging sightings and zoo visits. These components are used
// within the dashboard to submit data to the FastAPI backend.

// Form used to log a new animal sighting. When `animals` or `zoos` are not
// provided, they are fetched from the API. `defaultAnimalId` and
// `defaultZooId` pre‑select values but the user can search to change them.
export function LogSighting({
  animals: propAnimals = null,
  zoos: propZoos = null,
  defaultAnimalId = '',
  defaultZooId = '',
  defaultDate = null,
  initialAnimalName = '',
  initialZooName = '',
  defaultNotes = '',
  sightingId = null,
  titleId = '',
  onLogged,
  onCancel,
  onDeleted,
}: LogSightingProps) {
  const [animals, setAnimals] = useState<AnimalOption[]>(propAnimals ?? []);
  const [zoos, setZoos] = useState<ZooOption[]>(propZoos ?? []);
  const [animalId, setAnimalId] = useState(defaultAnimalId);
  const [zooId, setZooId] = useState(defaultZooId);
  // Inputs start with provided names so the form can show defaults
  const [animalInput, setAnimalInput] = useState(initialAnimalName);
  const [zooInput, setZooInput] = useState(initialZooName);
  const [zooFocused, setZooFocused] = useState(false);
  const [animalFocused, setAnimalFocused] = useState(false);
  const [zooActiveIndex, setZooActiveIndex] = useState(-1);
  const [animalActiveIndex, setAnimalActiveIndex] = useState(-1);
  const [notes, setNotes] = useState(defaultNotes);
  const { zoos: zooSuggestions } = useSearchSuggestions(zooInput, zooFocused);
  const { animals: animalSuggestions } = useSearchSuggestions(
    animalInput,
    animalFocused
  );
  // Wrapper for fetch that redirects to login on 401
  const authFetch = useAuthFetch();
  const { user } = useAuth();
  const { lang } = useParams();
  const getName = useCallback(
    (animal: AnimalOption | null | undefined) => {
      if (!animal) {
        return '';
      }
      return lang === 'de'
        ? animal.name_de || animal.name_en || ''
        : animal.name_en || animal.name_de || '';
    },
    [lang]
  );
  const { t } = useTranslation();
  const zooBaseId = useId();
  const zooFieldId = `log-sighting-zoo-${zooBaseId.replace(/:/g, '')}`;
  const zooListId = `${zooFieldId}-listbox`;
  const zooLabelId = `${zooFieldId}-label`;
  const animalBaseId = useId();
  const animalFieldId = `log-sighting-animal-${animalBaseId.replace(/:/g, '')}`;
  const animalListId = `${animalFieldId}-listbox`;
  const animalLabelId = `${animalFieldId}-label`;
  const dateBaseId = useId();
  const dateFieldId = `log-sighting-date-${dateBaseId.replace(/:/g, '')}`;
  const notesBaseId = useId();
  const notesFieldId = `log-sighting-notes-${notesBaseId.replace(/:/g, '')}`;
  const notesHelperId = `${notesFieldId}-helper`;
  // Date input defaults to today
    const initialDate = (defaultDate ?? new Date().toISOString().split('T')[0]) as string;
    const [sightingDate, setSightingDate] = useState<string>(initialDate);
  const zooBlurTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const animalBlurTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Update state if defaults change (e.g., after fetching an existing sighting)
  useEffect(() => {
    if (defaultAnimalId) setAnimalId(defaultAnimalId);
  }, [defaultAnimalId]);

  useEffect(() => {
    if (defaultZooId) setZooId(defaultZooId);
  }, [defaultZooId]);

  useEffect(() => {
    if (defaultDate) setSightingDate(defaultDate);
  }, [defaultDate]);

  useEffect(() => {
    setNotes(defaultNotes);
  }, [defaultNotes]);


  useEffect(() => {
    let cancelled = false;

    const loadAnimals = async () => {
      try {
        const response = await fetch(`${API}/animals`);
        if (cancelled) {
          return;
        }
        const data = await response.json();
        setAnimals(Array.isArray(data) ? (data as AnimalOption[]) : []);
      } catch {
        if (!cancelled) {
          setAnimals([]);
        }
      }
    };

    const loadZoos = async () => {
      try {
        const response = await fetch(`${API}/zoos?limit=6000`);
        const data = response.ok ? await response.json() : [];
        if (cancelled) {
          return;
        }
        if (Array.isArray(data?.items)) {
          setZoos((data.items ?? []) as ZooOption[]);
        } else if (Array.isArray(data)) {
          setZoos(data as ZooOption[]);
        } else {
          setZoos([]);
        }
      } catch {
        if (!cancelled) {
          setZoos([]);
        }
      }
    };

    if (!propAnimals) {
      void loadAnimals();
    }
    if (!propZoos) {
      void loadZoos();
    }

    return () => {
      cancelled = true;
    };
  }, [propAnimals, propZoos]);


  useEffect(() => {
    const match = animals.find((candidate) => candidate.id === (animalId || defaultAnimalId));
    if (match) setAnimalInput(getName(match));
  }, [animals, animalId, defaultAnimalId, getName]);

  useEffect(() => {
    const match = zoos.find((candidate) => candidate.id === (zooId || defaultZooId));
    if (match) setZooInput(getZooDisplayName(match));
  }, [zoos, zooId, defaultZooId]);

  useEffect(() => {
    if (zooActiveIndex >= zooSuggestions.length) {
      setZooActiveIndex(zooSuggestions.length - 1);
    }
  }, [zooActiveIndex, zooSuggestions.length]);

  useEffect(() => {
    if (animalActiveIndex >= animalSuggestions.length) {
      setAnimalActiveIndex(animalSuggestions.length - 1);
    }
  }, [animalActiveIndex, animalSuggestions.length]);

  useEffect(() => () => {
    if (zooBlurTimeout.current) clearTimeout(zooBlurTimeout.current);
    if (animalBlurTimeout.current) clearTimeout(animalBlurTimeout.current);
  }, []);

  const zooListOpen = zooFocused && zooSuggestions.length > 0;
  const animalListOpen = animalFocused && animalSuggestions.length > 0;

  const selectZoo = useCallback((z: ZooOption | null | undefined) => {
    if (!z) return;
    if (zooBlurTimeout.current) {
      clearTimeout(zooBlurTimeout.current);
      zooBlurTimeout.current = null;
    }
    setZooId(z.id);
    setZooInput(getZooDisplayName(z));
    setZooFocused(false);
    setZooActiveIndex(-1);
  }, []);

  const selectAnimal = useCallback((a: AnimalOption | null | undefined) => {
    if (!a) return;
    if (animalBlurTimeout.current) {
      clearTimeout(animalBlurTimeout.current);
      animalBlurTimeout.current = null;
    }
    setAnimalId(a.id);
    setAnimalInput(getName(a));
    setAnimalFocused(false);
    setAnimalActiveIndex(-1);
  }, [getName]);

  const handleZooKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      if (!zooSuggestions.length) return;
      event.preventDefault();
      setZooFocused(true);
      setZooActiveIndex((prev) => {
        if (prev < 0) return 0;
        const next = prev + 1;
        return next >= zooSuggestions.length ? 0 : next;
      });
    } else if (event.key === 'ArrowUp') {
      if (!zooSuggestions.length) return;
      event.preventDefault();
      setZooFocused(true);
      setZooActiveIndex((prev) => {
        if (prev < 0) return zooSuggestions.length - 1;
        const next = prev - 1;
        return next < 0 ? zooSuggestions.length - 1 : next;
      });
    } else if (event.key === 'Enter') {
      if (!zooListOpen) return;
      if (zooActiveIndex < 0 || zooActiveIndex >= zooSuggestions.length) return;
      event.preventDefault();
      selectZoo(zooSuggestions[zooActiveIndex]);
    } else if (event.key === 'Escape') {
      if (!zooListOpen) return;
      event.preventDefault();
      setZooFocused(false);
      setZooActiveIndex(-1);
    } else if (event.key === 'Tab') {
      setZooActiveIndex(-1);
      setZooFocused(false);
    }
  };

  const handleAnimalKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      if (!animalSuggestions.length) return;
      event.preventDefault();
      setAnimalFocused(true);
      setAnimalActiveIndex((prev) => {
        if (prev < 0) return 0;
        const next = prev + 1;
        return next >= animalSuggestions.length ? 0 : next;
      });
    } else if (event.key === 'ArrowUp') {
      if (!animalSuggestions.length) return;
      event.preventDefault();
      setAnimalFocused(true);
      setAnimalActiveIndex((prev) => {
        if (prev < 0) return animalSuggestions.length - 1;
        const next = prev - 1;
        return next < 0 ? animalSuggestions.length - 1 : next;
      });
    } else if (event.key === 'Enter') {
      if (!animalListOpen) return;
      if (animalActiveIndex < 0 || animalActiveIndex >= animalSuggestions.length)
        return;
      event.preventDefault();
      selectAnimal(animalSuggestions[animalActiveIndex]);
    } else if (event.key === 'Escape') {
      if (!animalListOpen) return;
      event.preventDefault();
      setAnimalFocused(false);
      setAnimalActiveIndex(-1);
    } else if (event.key === 'Tab') {
      setAnimalActiveIndex(-1);
      setAnimalFocused(false);
    }
  };

    const zooActiveSuggestion =
      zooListOpen &&
      zooActiveIndex >= 0 &&
      zooActiveIndex < zooSuggestions.length
        ? zooSuggestions[zooActiveIndex]
        : undefined;
    const zooActiveId = zooActiveSuggestion
      ? `${zooListId}-z-${
          typeof zooActiveSuggestion.slug === 'string' && zooActiveSuggestion.slug.length > 0
            ? zooActiveSuggestion.slug
            : zooActiveSuggestion.id
        }`
      : undefined;

    const animalActiveSuggestion =
      animalListOpen &&
      animalActiveIndex >= 0 &&
      animalActiveIndex < animalSuggestions.length
        ? animalSuggestions[animalActiveIndex]
        : undefined;
    const animalActiveId = animalActiveSuggestion
      ? `${animalListId}-a-${
          typeof animalActiveSuggestion.slug === 'string' && animalActiveSuggestion.slug.length > 0
            ? animalActiveSuggestion.slug
            : animalActiveSuggestion.id
        }`
      : undefined;

  // Send a new sighting to the API for the selected animal and zoo.
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const uid = user?.id;
    if (!uid) {
      alert('User not available');
      return;
    }
    if (!zooId || !animalId) {
      alert('Please choose a zoo and animal');
      return;
    }
    const sighting: Pick<Sighting, 'zoo_id' | 'animal_id' | 'sighting_datetime'> & {
      notes?: string | null;
    } = {
      zoo_id: zooId,
      animal_id: animalId,
      sighting_datetime: new Date(sightingDate).toISOString(),
    };
    const trimmedNotes = notes.trim();
    if (trimmedNotes) {
      sighting.notes = trimmedNotes;
    } else if (sightingId) {
      sighting.notes = null;
    }
    const url = sightingId ? `${API}/sightings/${sightingId}` : `${API}/sightings`;
    const method = sightingId ? 'PATCH' : 'POST';
    const resp = await authFetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(sighting)
    });
    if (resp.status === 401) return;
    if (resp.ok) {
      onLogged?.();
    } else {
      alert('Failed to save sighting');
    }
  };

  const handleDelete = async () => {
    if (!sightingId) return;
    const resp = await authFetch(`${API}/sightings/${sightingId}`, {
      method: 'DELETE'
    });
    if (resp.status === 401) return;
    if (resp.ok) {
      onDeleted?.();
    } else {
      alert('Failed to delete sighting');
    }
  };

  return (
    <form onSubmit={submit} className="mb-3">
      <h3 id={titleId || undefined}>
        {sightingId
          ? t('forms.sighting.titleEdit')
          : t('forms.sighting.titleNew')}
      </h3>
      <div className="mb-2 position-relative">
        {/* Searchable zoo field */}
        <label className="form-label" htmlFor={zooFieldId} id={zooLabelId}>
          {t('forms.sighting.zooLabel')}
        </label>
        <input
          className="form-control"
          placeholder={t('forms.sighting.zooPlaceholder')}
          value={zooInput}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            const val = event.target.value;
            setZooInput(val);
            setZooId('');
            setZooActiveIndex(-1);
          }}
          onFocus={() => {
            if (zooBlurTimeout.current) {
              clearTimeout(zooBlurTimeout.current);
              zooBlurTimeout.current = null;
            }
            setZooFocused(true);
          }}
          onBlur={() => {
            zooBlurTimeout.current = setTimeout(() => {
              setZooFocused(false);
              setZooActiveIndex(-1);
              zooBlurTimeout.current = null;
            }, 100);
          }}
          onKeyDown={handleZooKeyDown}
          required
          id={zooFieldId}
          role="combobox"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-expanded={zooListOpen}
          aria-controls={zooListOpen ? zooListId : undefined}
          aria-activedescendant={zooActiveId}
          autoComplete="off"
        />
        {zooListOpen && (
          <ul
            className="list-group position-absolute top-100 start-0 search-suggestions"
            role="listbox"
            id={zooListId}
            aria-labelledby={zooLabelId}
          >
              {zooSuggestions.map((z, index) => {
                let keyValue: string;
                if (typeof z.slug === 'string' && z.slug.length > 0) {
                  keyValue = z.slug;
                } else if (typeof z.id === 'string') {
                  keyValue = z.id;
                } else if (typeof z.id === 'number') {
                  keyValue = String(z.id);
                } else {
                  keyValue = String(index);
                }
                const optionId = `${zooListId}-z-${keyValue}`;
                const isActive = index === zooActiveIndex;
                return (
                  <li
                    key={keyValue}
                    id={optionId}
                  role="option"
                  aria-selected={isActive ? 'true' : 'false'}
                  className={`list-group-item${isActive ? ' active' : ''}`}
                  onPointerDown={(pointerEvent) => {
                    pointerEvent.preventDefault();
                    selectZoo(z);
                  }}
                  onMouseEnter={() => { setZooActiveIndex(index); }}
                  onMouseMove={() => { setZooActiveIndex(index); }}
                >
                  {getZooDisplayName(z)}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="mb-2 position-relative">
        {/* Searchable animal field */}
        <label className="form-label" htmlFor={animalFieldId} id={animalLabelId}>
          {t('forms.sighting.animalLabel')}
        </label>
        <input
          className="form-control"
          placeholder={t('forms.sighting.animalPlaceholder')}
          value={animalInput}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            const val = event.target.value;
            setAnimalInput(val);
            setAnimalId('');
            setAnimalActiveIndex(-1);
          }}
          onFocus={() => {
            if (animalBlurTimeout.current) {
              clearTimeout(animalBlurTimeout.current);
              animalBlurTimeout.current = null;
            }
            setAnimalFocused(true);
          }}
          onBlur={() => {
            animalBlurTimeout.current = setTimeout(() => {
              setAnimalFocused(false);
              setAnimalActiveIndex(-1);
              animalBlurTimeout.current = null;
            }, 100);
          }}
          onKeyDown={handleAnimalKeyDown}
          required
          id={animalFieldId}
          role="combobox"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-expanded={animalListOpen}
          aria-controls={animalListOpen ? animalListId : undefined}
          aria-activedescendant={animalActiveId}
          autoComplete="off"
        />
        {animalListOpen && (
          <ul
            className="list-group position-absolute top-100 start-0 search-suggestions"
            role="listbox"
            id={animalListId}
            aria-labelledby={animalLabelId}
          >
              {animalSuggestions.map((a, index) => {
                let keyValue: string;
                if (typeof a.slug === 'string' && a.slug.length > 0) {
                  keyValue = a.slug;
                } else if (typeof a.id === 'string') {
                  keyValue = a.id;
                } else if (typeof a.id === 'number') {
                  keyValue = String(a.id);
                } else {
                  keyValue = String(index);
                }
                const optionId = `${animalListId}-a-${keyValue}`;
                const isActive = index === animalActiveIndex;
                return (
                  <li
                    key={keyValue}
                  id={optionId}
                  role="option"
                  aria-selected={isActive ? 'true' : 'false'}
                  className={`list-group-item${isActive ? ' active' : ''}`}
                  onPointerDown={(pointerEvent) => {
                    pointerEvent.preventDefault();
                    selectAnimal(a);
                  }}
                  onMouseEnter={() => { setAnimalActiveIndex(index); }}
                  onMouseMove={() => { setAnimalActiveIndex(index); }}
                >
                  {getName(a)}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="mb-2">
        <label className="form-label" htmlFor={dateFieldId}>
          {t('forms.sighting.dateLabel')}
        </label>
        <input
          className="form-control"
          type="date"
          value={sightingDate}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            setSightingDate(event.target.value);
          }}
          required
          id={dateFieldId}
        />
      </div>
      <div className="mb-3">
        <label className="form-label" htmlFor={notesFieldId}>
          {t('forms.sighting.notesLabel')}
        </label>
        <textarea
          className="form-control"
          id={notesFieldId}
          placeholder={t('forms.sighting.notesPlaceholder')}
          value={notes}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => {
            setNotes(event.target.value);
          }}
          maxLength={1000}
          rows={3}
          aria-describedby={notesHelperId}
        />
        <div className="form-text" id={notesHelperId}>
          {t('forms.sighting.notesHelper', { count: 1000 - notes.length })}
        </div>
      </div>
      <div className="text-end">
        {onCancel && (
          <button
            type="button"
            className="btn btn-outline-danger me-2"
            onClick={onCancel}
          >
            {t('forms.sighting.cancel')}
          </button>
        )}
        {sightingId && (
          <button
            type="button"
            className="btn btn-danger me-2"
            onClick={handleDelete}
          >
            {t('forms.sighting.delete')}
          </button>
        )}
        <button className="btn btn-primary" type="submit">
          {sightingId
            ? t('forms.sighting.submitUpdate')
            : t('forms.sighting.submitCreate')}
        </button>
      </div>
    </form>
  );
}

