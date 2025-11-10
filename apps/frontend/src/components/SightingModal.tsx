import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import { useState, useEffect, useRef, useId, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useParams } from 'react-router-dom';

import { LogSighting, type AnimalOption, type ZooOption } from './logForms';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import type { Sighting } from '../types/domain';

interface SightingModalProps {
  sightingId?: string | null;
  defaultZooId?: string;
  defaultAnimalId?: string;
  defaultZooName?: string;
  defaultAnimalName?: string;
  defaultNotes?: string;
  zoos?: ZooOption[] | null;
  animals?: AnimalOption[] | null;
  onLogged?: () => void;
  onUpdated?: () => void;
  onClose?: () => void;
}

// Modal wrapper for creating or editing sightings. When a `sightingId`
// is provided the existing entry is loaded and the form works in edit mode.
export default function SightingModal({
  sightingId = null,
  defaultZooId = '',
  defaultAnimalId = '',
  defaultZooName = '',
  defaultAnimalName = '',
  defaultNotes = '',
  zoos: propZoos = null,
  animals: propAnimals = null,
  onLogged,
  onUpdated,
  onClose,
}: SightingModalProps) {
  const [zoos, setZoos] = useState<ZooOption[]>(propZoos ?? []);
  const [animals, setAnimals] = useState<AnimalOption[]>(propAnimals ?? []);
  const [sighting, setSighting] = useState<Sighting | null>(null);
  const authFetch = useAuthFetch();
  const { lang } = useParams();
  const getName = useCallback(
    (animal: AnimalOption | null | undefined) => {
      if (!animal) return '';
      return lang === 'de'
        ? animal.name_de || animal.name_en || ''
        : animal.name_en || animal.name_de || '';
    },
    [lang]
  );
  const modalRef = useRef<HTMLDivElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const titleId = `sighting-modal-title-${useId().replace(/:/g, '')}`;
  const [portalNode] = useState<HTMLDivElement | null>(() => {
    if (typeof document === 'undefined') return null;
    const node = document.createElement('div');
    node.className = 'modal-portal';
    return node;
  });

  // Load zoo list when none were provided
  useEffect(() => {
    const loadZoos = async () => {
      if (propZoos && propZoos.length > 0) {
        setZoos(propZoos);
        return;
      }
      try {
        const resp = await fetch(`${API}/zoos?limit=6000`);
        if (resp.ok) {
          const payload = (await resp.json()) as unknown;
          const items = Array.isArray((payload as { items?: unknown }).items)
            ? (payload as { items: ZooOption[] }).items
            : Array.isArray(payload)
              ? (payload as ZooOption[])
              : [];
          setZoos(items);
        }
      } catch {
        setZoos([]);
      }
    };
    void loadZoos();
  }, [propZoos]);

  // Load animal list when none were provided
  useEffect(() => {
    const loadAnimals = async () => {
      if (propAnimals && propAnimals.length > 0) {
        setAnimals(propAnimals);
        return;
      }
      try {
        const resp = await fetch(`${API}/animals`);
        if (resp.ok) {
          const payload = (await resp.json()) as unknown;
          setAnimals(Array.isArray(payload) ? (payload as AnimalOption[]) : []);
        }
      } catch {
        setAnimals([]);
      }
    };
    void loadAnimals();
  }, [propAnimals]);

  // Fetch existing sighting when editing
  useEffect(() => {
    if (!sightingId) return;
    const loadSighting = async () => {
      try {
        const resp = await authFetch(`${API}/sightings/${sightingId}`);
        if (resp.ok) {
          const payload = (await resp.json()) as unknown;
          if (payload && typeof payload === 'object') {
            setSighting(payload as Sighting);
          } else {
            setSighting(null);
          }
        }
      } catch {
        setSighting(null);
      }
    };
    void loadSighting();
  }, [sightingId, authFetch]);

  // Notify parent and close the modal after saving or deleting
  const handleDone = () => {
    if (sightingId) {
      onUpdated?.();
    } else {
      onLogged?.();
    }
    onClose?.();
  };

  useEffect(() => {
    if (!portalNode || typeof document === 'undefined') return undefined;
    document.body.appendChild(portalNode);
    return () => {
      document.body.removeChild(portalNode);
    };
  }, [portalNode]);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const active = document.activeElement;
    if (active instanceof HTMLElement) {
      previouslyFocused.current = active;
    }
    const focusableSelector =
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const focusModal = () => {
      const modalNode = modalRef.current;
      if (!modalNode) return;
      const focusableElements = Array.from(
        modalNode.querySelectorAll<HTMLElement>(focusableSelector)
      );
      const firstFocusable = focusableElements[0];
      if (firstFocusable) {
        firstFocusable.focus();
      } else {
        modalNode.focus();
      }
  };
    const focusTimeout = window.setTimeout(focusModal, 0);
    return () => {
      window.clearTimeout(focusTimeout);
      const prev = previouslyFocused.current;
      if (prev && typeof prev.focus === 'function') {
        prev.focus();
      }
    };
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const appRoot = document.getElementById('root');
    const previousHidden = appRoot?.getAttribute('aria-hidden') ?? null;
    const hadInert = appRoot?.hasAttribute('inert') ?? false;
    if (appRoot) {
      appRoot.setAttribute('aria-hidden', 'true');
      appRoot.setAttribute('inert', '');
    }
    return () => {
      document.body.style.overflow = previousOverflow;
      if (appRoot) {
        if (previousHidden === null) {
          appRoot.removeAttribute('aria-hidden');
        } else {
          appRoot.setAttribute('aria-hidden', previousHidden);
        }
        if (hadInert) {
          appRoot.setAttribute('inert', '');
        } else {
          appRoot.removeAttribute('inert');
        }
      }
    };
  }, []);

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      const modalNode = modalRef.current;
      if (!modalNode) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose?.();
        return;
      }
      if (event.key !== 'Tab') return;
        const focusableElements = Array.from(
          modalNode.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        );
        if (focusableElements.length === 0) {
          event.preventDefault();
          modalNode.focus();
          return;
        }
        const first = focusableElements[0];
        const last = focusableElements[focusableElements.length - 1];
        if (!first || !last) {
          event.preventDefault();
          modalNode.focus();
          return;
        }
        const active = document.activeElement;
        if (event.shiftKey) {
          if (!active || !modalNode.contains(active) || active === first) {
            event.preventDefault();
            last.focus();
          }
        } else if (!active || !modalNode.contains(active) || active === last) {
          event.preventDefault();
          first.focus();
        }
    },
    [onClose]
  );

  if (!portalNode) {
    return null;
  }

  return createPortal(
    <div
      className="modal-overlay"
      role="presentation"
      ref={overlayRef}
      onKeyDown={handleKeyDown}
    >
      <div
        className="modal-box"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={modalRef}
        tabIndex={-1}
      >
        <LogSighting
          zoos={zoos}
          animals={animals}
          defaultZooId={sighting ? sighting.zoo_id : defaultZooId}
          defaultAnimalId={sighting ? sighting.animal_id : defaultAnimalId}
            defaultDate={sighting ? sighting.sighting_datetime.slice(0, 10) : null}
          initialZooName={
            sighting
              ? (() => {
                  const match = zoos.find((z) => z.id === sighting.zoo_id);
                  if (!match) {
                    return defaultZooName;
                  }
                  return match.name || defaultZooName;
                })()
              : defaultZooName
          }
          initialAnimalName={
            sighting
              ? (() => {
                  const match = animals.find((a) => a.id === sighting.animal_id);
                  const resolved = getName(match);
                  return resolved || defaultAnimalName;
                })()
              : defaultAnimalName
          }
          defaultNotes={sighting ? sighting.notes ?? '' : defaultNotes}
          sightingId={sightingId}
          onLogged={handleDone}
          onDeleted={handleDone}
          onCancel={() => onClose?.()}
          titleId={titleId}
        />
      </div>
    </div>,
    portalNode
  );
}

