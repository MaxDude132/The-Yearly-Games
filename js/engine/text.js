// Turns story templates like "{a} kills {b}" into finished [english, french] sentences.

// Invisible markers around tribute names, so the screen can show them in bold.
export const NAME_START = '\u0001';
export const NAME_END = '\u0002';

export const nameTag = (tribute) => NAME_START + tribute.name + NAME_END;

/**
 * Fills a template pair with values.
 * A value can be a tribute (shown as its name), an [english, french] pair, or a plain number/string.
 */
export function formatText(templatePair, values = {}) {
  return templatePair.map((template, language) =>
    template.replace(/\{(\w+)\}/g, (placeholder, key) => {
      const value = values[key];
      if (Array.isArray(value)) return value[language];
      if (value && typeof value.name === 'string') return nameTag(value);
      return value;
    }),
  );
}
