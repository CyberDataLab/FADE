export interface Scenario {
    id: number;          
    name: string;
    design: object;      
    uuid: string;
    status: 'draft' | 'running' | 'finished';
    date: string;
}