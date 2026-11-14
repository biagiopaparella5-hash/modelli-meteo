// Indirizzo dove GitHub Actions pubblica mappe e manifest (GitHub Pages del repository).
// Se rinomini il repository o cambi account, modifica solo questa riga.
window.DATA_URL = "https://biagiopaparella5-hash.github.io/modelli-meteo/";

// Modelli usati nella sezione Località (servizio gratuito Open-Meteo)
window.POINT_MODELS = [
  { id: "ecmwf_ifs025",         label: "ECMWF",   color: "#22c55e" },
  { id: "gfs_seamless",         label: "GFS",     color: "#4f8cff" },
  { id: "icon_seamless",        label: "ICON",    color: "#f59e0b" },
  { id: "gem_seamless",         label: "GEM",     color: "#e879f9" },
  { id: "meteofrance_seamless", label: "ARPEGE",  color: "#38bdf8" },
  { id: "ukmo_seamless",        label: "UKMO",    color: "#f87171" },
];
