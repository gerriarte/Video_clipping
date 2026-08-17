import { Config } from "@remotion/cli/config";

// Remotion no encodea el DOM directo: saca cada frame como imagen y se la pasa a
// ffmpeg. Con "jpeg" y sin calidad explícita usa 80 (DEFAULT_JPEG_QUALITY), o sea
// que TODOS los frames pasan por una compresión con pérdida ANTES del x264. Eso
// se ve como bloques en los degradados y halo alrededor de los bordes y el texto.
// 100 es prácticamente sin pérdida y sigue siendo mucho más rápido que "png".
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(100);

// El JPEG intermedio entra en rango completo (0–255) y sin esto la salida queda
// etiquetada yuvj420p: cada reproductor la interpreta distinto y el material se
// ve lavado o con negros aplastados. bt709 es lo que espera cualquier red social.
Config.setColorSpace("bt709");

// A mismo CRF, "slow" da la misma calidad en menos bits (o más calidad en los
// mismos). El cuello de botella del render es Chromium sacando frames, no x264:
// el encode más lento casi no se nota en el total.
Config.setX264Preset("slow");

Config.setOverwriteOutput(true);
