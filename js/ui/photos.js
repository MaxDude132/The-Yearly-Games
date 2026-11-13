// Shrinks a chosen photo to a small square so 24 of them fit in browser storage.
const PHOTO_SIZE = 96; // pixels

/** Resolves to a JPEG data URL of the photo, cropped to a centred square. */
export function photoToSmallSquare(file) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(file);

    image.onload = () => {
      const side = Math.min(image.width, image.height);
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = PHOTO_SIZE;
      canvas.getContext('2d').drawImage(
        image,
        (image.width - side) / 2, (image.height - side) / 2, side, side,
        0, 0, PHOTO_SIZE, PHOTO_SIZE,
      );
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', 0.8));
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('This file is not an image the browser can read.'));
    };

    image.src = url;
  });
}
