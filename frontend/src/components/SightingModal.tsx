// @ts-nocheck
import { useState, useEffect, useRef, useId, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useParams } from 'react-router-dom';

import { LogSighting } from './logForms';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

// Modal wrapper for creating or editing sightings. When a `sightingId`
// is provided the existing entry is loaded and the form works in edit mode.
export default function SightingModal({
  sightingId = null,
  defaultZooId = '',
  defaultAnimalId = '',
  defaultZooName = '',
  defaultAnimalName = '',
  defaultNotes = '',
  // Optional pre-fetched lists to skip fetching inside the modal
  zoos: propZoos = null,
  animals: propAnimals = null,
  onLogged,
  onUpdated,
  onClose,
}: any) {
  // Start with provided lists if available
  const [zoos, setZoos] = useState(propZoos || []);
  const [animals, setAnimals] = useState(propAnimals || []);
  const [sighting, setSighting] = useState<any>(null);
  const authFetch = useAuthFetch();
  const { lang } = useParams();
  const getName = (a) =>
    lang === 'de' ? a.name_de || a.name_en : a.name_en || a.name_de;
  const modalRef = useRef<any>(null);
  const overlayRef = useRef<any>(null);
  const previouslyFocused = useRef<any>(null);
  const titleId = `sighting-modal-title-${useId().replace(/:/g, '')}`;
  const [portalNode] = useState(() => {
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
          const payload = await resp.json();
          const items = Array.isArray(payload?.items)
            ? payload.items
            : Array.isArray(payload)
              ? payload
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
        if (resp.ok) setAnimals(await resp.json());
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
        if (resp.ok) setSighting(await resp.json());
      } catch {
        setSighting(null);
      }
    };
    void loadSighting();
  }, [sightingId, authFetch]);

  // Notify parent and close the modal after saving or deleting
  const handleDone = () => {
    if (sightingId) {
      onUpdated && onUpdated();
    } else {
      onLogged && onLogged();
    }
    onClose && onClose();
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
      const focusable = modalNode.querySelectorAll(focusableSelector);
      if (focusable.length > 0) {
        focusable[0].focus();
      } else {
        modalNode.focus();
      }
    };
    const focusTimeout = setTimeout(focusModal, 0);
    return () => {
      clearTimeout(focusTimeout);
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
    const hadInert = appRoot?.hasAttribute('inert');
    if (appRoot) {
      appRoot.setAttribute('aria-hidden', 'true');
      appRoot.setAttribute('inert', '');
    }
    return () => {
      document.body.style.overflow = previousOverflow;
      if (appRoot) {
        if (previousHidden === null) appRoot.removeAttribute('aria-hidden');
        else appRoot.setAttribute('aria-hidden', previousHidden ?? 'false');
        if (hadInert) appRoot.setAttribute('inert', '');
        else appRoot.removeAttribute('inert');
      }
    };
  }, []);

  const handleKeyDown = useCallback(
    (event) => {
      const modalNode = modalRef.current;
      if (!modalNode) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose && onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = modalNode.querySelectorAll(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) {
        event.preventDefault();
        modalNode.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (!modalNode.contains(active) || active === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (!modalNode.contains(active) || active === last) {
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
          defaultDate={
            sighting ? sighting.sighting_datetime.slice(0, 10) : undefined
          }
          initialZooName={
            sighting
              ? zoos.find((z) => z.id === sighting.zoo_id)?.name || defaultZooName
              : defaultZooName
          }
          initialAnimalName={
            sighting
              ? getName(
                  animals.find((a) => a.id === sighting.animal_id) || {}
                ) || defaultAnimalName
              : defaultAnimalName
          }
          defaultNotes={sighting ? sighting.notes ?? '' : defaultNotes}
          sightingId={sightingId}
          onLogged={handleDone}
          onDeleted={handleDone}
          onCancel={() => onClose && onClose()}
          titleId={titleId}
        />
      </div>
    </div>,
    portalNode
  );
}

