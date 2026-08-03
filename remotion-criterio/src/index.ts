import { registerRoot } from 'remotion';
import { loadFont as loadArchivo } from '@remotion/google-fonts/Archivo';
import { loadFont as loadArchivoBlack } from '@remotion/google-fonts/ArchivoBlack';
import { RemotionRoot } from './Root';

// Las tipografías del sistema de diseño (ver theme.ts). Sin esto el render
// cae a la sans del sistema y el display type —que es medio episodio—
// pierde el peso que lo sostiene.
// Solo los pesos y el subset que usa el theme: cargarlos todos son ~50
// pedidos de red por frame de arranque y el render depende de que la red
// esté ahí.
loadArchivo('normal', { weights: ['500', '600'], subsets: ['latin'] });
loadArchivoBlack('normal', { subsets: ['latin'] });

registerRoot(RemotionRoot);
