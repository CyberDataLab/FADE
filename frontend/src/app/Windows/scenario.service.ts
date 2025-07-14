import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { Subject, Observable, EMPTY, switchMap, catchError, throwError } from 'rxjs';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { isPlatformBrowser } from '@angular/common';

@Injectable({ providedIn: 'root' })
export class ScenarioService {
  private hasUnsavedChanges = false;
  private saveRequested = new Subject<void>();

  saveRequested$ = this.saveRequested.asObservable();

  private apiUrl = 'http://localhost:8000/data/scenarios/';
  private authUrl = 'http://localhost:8000/token/'; 
  constructor(@Inject(PLATFORM_ID) private platformId: Object, private http: HttpClient) {}

  setUnsavedChanges(state: boolean): void {
    this.hasUnsavedChanges = state;
  }

  getUnsavedChanges(): boolean {
    return this.hasUnsavedChanges;
  }

  requestSave(): void {
    this.saveRequested.next();
  }

  private getToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('access_token');
    }
    return null;
  }

  private getRefreshToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('refresh_token');
    }
    return null;
  }

  private saveTokens(accessToken: string, refreshToken: string): void {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  getAuthHeaders(): HttpHeaders {
    const token = this.getToken();
    return new HttpHeaders({
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    });
  }

  private getAuthHeadersWithoutContentType(): HttpHeaders {
    const token = this.getToken();
    return new HttpHeaders({
      Authorization: token ? `Bearer ${token}` : '',
    });
  }

  private refreshToken(): Observable<any> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      return throwError(() => new Error('No refresh token available'));
    }
  
    return this.http.post(`${this.authUrl}refresh/`, { refresh: refreshToken }).pipe(
      switchMap((response: any) => {
        this.saveTokens(response.access, refreshToken);
        return response.access;
      }),
      catchError((error: any) => {
        console.error('Error refreshing token', error);
        this.logout();
        return throwError(() => error);
      })
    );
  }

  handleRequest<T>(request: Observable<T>): Observable<T> {
    return request.pipe(
      catchError((error:any) => {
        if (error.status === 401) {
          return this.refreshToken().pipe(
            switchMap(() => request), 
            catchError(() => {
              this.logout();
              return EMPTY;
            })
          );
        }
        return throwError(() => error);
      })
    );
  }

  saveScenario(name: string, design: any, csvFiles?: File[], networkFiles?: File[]): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      const formData = new FormData();
      formData.append('name', name);
      formData.append('design', JSON.stringify(design));
  
  
      if (csvFiles && csvFiles.length > 0) {
        csvFiles.forEach(file => {
          formData.append('csv_files', file);
        });
      }
  
      if (networkFiles && networkFiles.length > 0) {
        networkFiles.forEach(file => {
          formData.append('network_files', file);
        });
      }
    
      return this.handleRequest(this.http.post(this.apiUrl + 'create/', formData, {
        headers: this.getAuthHeadersWithoutContentType(),
      }));
    }
  
    return EMPTY;
  }
  
  editScenario(uuid: string, design: any, csvFiles?: File[], networkFiles?: File[]): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      const formData = new FormData();
      formData.append('design', JSON.stringify(design));
  
      if (csvFiles && csvFiles.length > 0) {
        csvFiles.forEach(file => formData.append('csv_files', file));
      }
  
      if (networkFiles && networkFiles.length > 0) {
        networkFiles.forEach(file => formData.append('network_files', file));
      }
  
      return this.handleRequest(this.http.put(`${this.apiUrl}put/${uuid}/`, formData, {
        headers: this.getAuthHeadersWithoutContentType(),
      }));
    }
  
    return EMPTY;
  }
  
  getScenarios(): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(this.http.get(this.apiUrl, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }

  getScenarioById(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {  
      return this.handleRequest(this.http.get(`${this.apiUrl}${uuid}/`, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }

  runScenario(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(this.http.patch(`${this.apiUrl}run/${uuid}/`, null, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }
  
  deleteScenario(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(this.http.delete(`${this.apiUrl}delete/${uuid}/`, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }
  
  getScenarioClassificationMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/classification-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  getScenarioRegressionMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/regression-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  getScenarioAnomalyMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/anomaly-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  getScenarioProductionAnomalyMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/anomaly-production-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  playProduction(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.post(`${this.apiUrl}${uuid}/play-production/`, {}, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  stopProduction(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.post(`${this.apiUrl}${uuid}/stop-production/`, {}, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  deleteAnomaly(uuid: string, anomalyId: number): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.delete(`${this.apiUrl}${uuid}/delete-anomaly/${anomalyId}/`, {
          headers: this.getAuthHeaders()
        })
      );
    }
    return EMPTY;
  }
  
  logout(): void {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }
}
