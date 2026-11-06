/**
 * Configuración del portal.
 *
 * MODO SINTÉTICO (desarrollo, sin DW):
 *   Dejar API_URL = '' → usa los datos de data/synthetic.js
 *
 * MODO REAL (DW de Jhair disponible):
 *   Cambiar API_URL a la URL de la API en la VM, por ejemplo:
 *   const API_URL = 'http://157.137.227.1:8000/api/v1';
 *   O si hay dominio: 'https://api.equiframe.ec/api/v1';
 */
const API_URL = '';   // ← cambiar a URL real cuando el DW esté listo

const EQ_CONFIG = {
  apiUrl:     API_URL,
  useRealApi: API_URL !== '',
  snapshotId: '20261012-v1',
};
