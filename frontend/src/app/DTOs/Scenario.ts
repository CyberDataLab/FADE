export interface Scenario {
    id: number;          
    name: string;
    design: object;      
    uuid: string;
    status: 'Draft' | 'Running' | 'Finished';
    date: string;
}