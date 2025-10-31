const SUPPORTED_LANGUAGES = new Set(['en', 'de']);

function normalizeLanguage(language) {
  if (typeof language !== 'string') {
    return 'en';
  }
  const base = language.split('-')[0]?.toLowerCase() ?? '';
  return SUPPORTED_LANGUAGES.has(base) ? base : 'en';
}

function buildTextFieldExpression(language) {
  const candidateFields = [`name:${language}`, 'name:en', 'name:latin', 'name'];
  const uniqueFields = Array.from(new Set(candidateFields.filter(Boolean)));
  const fallbacks = uniqueFields.map((field) => ['get', field]);
  return ['coalesce', ...fallbacks];
}

function expressionUsesNameField(value) {
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
    return Object.values(value).some(expressionUsesNameField);
  }
  return false;
}

export function applyBaseMapLanguage(map, language) {
  if (!map) return;
  const normalized = normalizeLanguage(language);

  const apply = () => {
    if (!map.getStyle || typeof map.getStyle !== 'function') return;
    const style = map.getStyle();
    if (!style?.layers || !Array.isArray(style.layers)) return;
    const textField = buildTextFieldExpression(normalized);

    style.layers.forEach((layer) => {
      if (!layer || layer.type !== 'symbol') return;
      const layerLayout = layer.layout ?? {};
      if (!layerLayout['text-field']) return;
      if (!expressionUsesNameField(layerLayout['text-field'])) return;
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
      map.once('styledata', apply);
      return;
    }
  }

  apply();
}
