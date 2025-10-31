import type { Map as MaplibreMap, StyleSpecification } from 'maplibre-gl';

const SUPPORTED_LANGUAGES = new Set(['en', 'de']);

type TextExpression = ['coalesce', ...unknown[]];

function normalizeLanguage(language: unknown): 'en' | 'de' {
  if (typeof language !== 'string') {
    return 'en';
  }
  const base = language.split('-')[0]?.toLowerCase() ?? '';
  return SUPPORTED_LANGUAGES.has(base) ? (base as 'en' | 'de') : 'en';
}

function buildTextFieldExpression(language: 'en' | 'de'): TextExpression {
  const candidateFields = [`name:${language}`, 'name:en', 'name:latin', 'name'];
  const uniqueFields = Array.from(new Set(candidateFields.filter(Boolean)));
  const fallbacks = uniqueFields.map((field) => ['get', field]);
  return ['coalesce', ...fallbacks];
}

function expressionUsesNameField(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.includes('{name');
  }
  if (Array.isArray(value)) {
    if (value[0] === 'get' && typeof value[1] === 'string') {
      return value[1] === 'name' || value[1].startsWith('name:');
    }
    return value.some(expressionUsesNameField);
  }
  if (value && typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).some(expressionUsesNameField);
  }
  return false;
}

interface SymbolLayerLike {
  id: string;
  type?: string;
  layout?: Record<string, unknown>;
}

function isSymbolLayer(layer: unknown): layer is SymbolLayerLike {
  return Boolean(
    layer &&
    typeof (layer as SymbolLayerLike).id === 'string' &&
    (layer as SymbolLayerLike).type === 'symbol'
  );
}

export function applyBaseMapLanguage(map: MaplibreMap | null | undefined, language: unknown): void {
  if (!map) return;
  const normalized = normalizeLanguage(language);

  const apply = (): void => {
    const style: StyleSpecification | null | undefined = map.getStyle?.();
    if (!style?.layers || !Array.isArray(style.layers)) return;
    const textField = buildTextFieldExpression(normalized);

    style.layers.forEach((layer) => {
      if (!isSymbolLayer(layer)) return;
      const layerLayout = layer.layout ?? {};
      const textValue = layerLayout['text-field'];
      if (!textValue || !expressionUsesNameField(textValue)) return;
      if (typeof map.setLayoutProperty !== 'function') return;
      try {
        map.setLayoutProperty(layer.id, 'text-field', textField);
      } catch {
        // Ignore errors from attempts to update readonly layers.
      }
    });
  };

  if (typeof map.isStyleLoaded === 'function' && !map.isStyleLoaded()) {
    if (typeof map.once === 'function') {
      void map.once('styledata', apply);
      return;
    }
  }

  apply();
}
