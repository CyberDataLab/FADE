export interface Scenario {
    id: number;          // Asumo que es un ID numérico autoincremental
    name: string;
    design: object;      // Asumo que es un objeto JSON/estructura de diseño
    uuid: string;        // UUID en formato string
    status: 'draft' | 'running' | 'finished'; // Tipo unión para estados controlados
    date: string;          // Tipo fecha nativo
}