// Angular core and common modules
import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { Subject, Observable, EMPTY, switchMap, catchError, throwError } from 'rxjs';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { isPlatformBrowser } from '@angular/common';

/**
 * @summary Service for managing visual scenario lifecycle and production execution.
 * 
 * Handles token authentication, design persistence, model execution, metric retrieval, and production control.
 */
@Injectable({
  providedIn: 'root'
})
export class ScenarioService {
  
  /** @summary Flag indicating if the current scenario has unsaved changes */
  private hasUnsavedChanges = false;

  /** @summary Subject to notify subscribers that a save has been requested */
  private saveRequested = new Subject<void>();
  saveRequested$ = this.saveRequested.asObservable();

  /** @summary Base API URL for scenario endpoints */
  private apiUrl = 'http://localhost:8000/data/scenarios/';
  private authUrl = 'http://localhost:8000/token/';

  constructor(
    @Inject(PLATFORM_ID) private platformId: Object,
    private http: HttpClient
  ) {}

  /** 
   * @summary Marks scenario as having unsaved changes.
   * 
   * @param state Whether changes are pending
   */
  setUnsavedChanges(state: boolean): void {
    this.hasUnsavedChanges = state;
  }

  /**
   * @summary Returns whether the current scenario has unsaved changes.
   * 
   * @returns True if there are unsaved changes
   */
  getUnsavedChanges(): boolean {
    return this.hasUnsavedChanges;
  }

  /**
   * @summary Triggers save event via `saveRequested$`.
   */
  requestSave(): void {
    this.saveRequested.next();
  }

  /**
   * @summary Retrieves access token from local storage.
   * 
   * @returns Access token string or null
   */
  private getToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('access_token');
    }
    return null;
  }

  /**
   * @summary Retrieves refresh token from local storage.
   * 
   * @returns Refresh token string or null
   */
  private getRefreshToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('refresh_token');
    }
    return null;
  }

  /**
   * @summary Saves access and refresh tokens to local storage.
   * 
   * @param accessToken JWT access token
   * @param refreshToken JWT refresh token
   */
  private saveTokens(accessToken: string, refreshToken: string): void {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  /**
   * @summary Builds HTTP headers with `Authorization` and `Content-Type`.
   * 
   * @returns HttpHeaders with JWT bearer token
   */
  getAuthHeaders(): HttpHeaders {
    const token = this.getToken();
    return new HttpHeaders({
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    });
  }

  /**
   * @summary Builds HTTP headers with only `Authorization`.
   * 
   * @returns HttpHeaders with JWT bearer token
   */
  private getAuthHeadersWithoutContentType(): HttpHeaders {
    const token = this.getToken();
    return new HttpHeaders({
      Authorization: token ? `Bearer ${token}` : '',
    });
  }

  /**
   * @summary Renews access token using the refresh token.
   * 
   * @returns Observable with new access token
   */
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

  /**
   * @summary Handles requests with auto-refresh on token expiration.
   * 
   * @param request Observable request to execute
   * 
   * @returns Observable with response or empty on failure
   */
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

  /**
   * @summary Saves a new scenario with optional CSV and network files.
   * 
   * @param name Scenario name
   * @param design Serialized design object
   * @param csvFiles Optional CSV files
   * @param networkFiles Optional PCAP or related files
   * 
   * @returns Observable with backend response
   */
  saveScenario(name: string, design: any, csvFiles?: File[], networkFiles?: File[], jsonlFiles?: File[]): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      const formData = new FormData();
      formData.append('name', name);
      formData.append('design', JSON.stringify(design));
  
      // Append CSV files to FormData if provided
      if (csvFiles && csvFiles.length > 0) {
        csvFiles.forEach(file => {
          formData.append('csv_files', file);
        });
      }
  
      // Append network files to FormData if provided
      if (networkFiles && networkFiles.length > 0) {
        networkFiles.forEach(file => {
          formData.append('network_files', file);
        });
      }

      // Append log files to FormData if provided
      if (jsonlFiles && jsonlFiles.length > 0) {
        jsonlFiles.forEach(file => {
          formData.append('jsonl_files', file);
        });
      }
    
      return this.handleRequest(this.http.post(this.apiUrl + 'create/', formData, {
        headers: this.getAuthHeadersWithoutContentType(),
      }));
    }
  
    return EMPTY;
  }
  
  /**
   * @summary Edits an existing scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * @param design Updated design object
   * @param csvFiles Optional CSV files
   * @param networkFiles Optional PCAP or related files
   * 
   * @returns Observable with response
   */
  editScenario(uuid: string, design: any, csvFiles?: File[], networkFiles?: File[], jsonlFiles?: File[]): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      const formData = new FormData();
      formData.append('design', JSON.stringify(design));
  
      // Append CSV files to FormData if provided
      if (csvFiles && csvFiles.length > 0) {
        csvFiles.forEach(file => formData.append('csv_files', file));
      }
  
      // Append network files to FormData if provided
      if (networkFiles && networkFiles.length > 0) {
        networkFiles.forEach(file => formData.append('network_files', file));
      }

      // Append log files to FormData if provided
      if (jsonlFiles && jsonlFiles.length > 0) {
        jsonlFiles.forEach(file => formData.append('jsonl_files', file));
      }
  
      return this.handleRequest(this.http.put(`${this.apiUrl}put/${uuid}/`, formData, {
        headers: this.getAuthHeadersWithoutContentType(),
      }));
    }
  
    return EMPTY;
  }
  
  /**
   * @summary Retrieves all saved scenarios.
   * 
   * @returns Observable with scenario list
   */
  getScenarios(): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(this.http.get(this.apiUrl, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }

  /**
   * @summary Retrieves a specific scenario by UUID.
   * 
   * @param uuid Unique scenario identifier
   * 
   * @returns Observable with scenario data
   */
  getScenarioById(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {  
      return this.handleRequest(this.http.get(`${this.apiUrl}${uuid}/`, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }

  /**
   * @summary Executes a scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with execution result
   */
  runScenario(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(this.http.patch(`${this.apiUrl}run/${uuid}/`, null, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }
  
  /**
   * @summary Deletes a scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with delete result
   */
  deleteScenario(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(this.http.delete(`${this.apiUrl}delete/${uuid}/`, { headers: this.getAuthHeaders() }));
    }
    return EMPTY;
  }
  
  /**
   * @summary Fetches classification metrics for a scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with metrics
   */
  getScenarioClassificationMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/classification-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  /**
   * @summary Fetches regression metrics for a scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with metrics
   */
  getScenarioRegressionMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/regression-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  /**
   * @summary Fetches anomaly detection metrics for a scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with anomaly metrics
   */
  getScenarioAnomalyMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/anomaly-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  /**
   * @summary Fetches production-time anomaly detection metrics by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with metrics
   */
  getScenarioProductionAnomalyMetrics(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.get(`${this.apiUrl}${uuid}/anomaly-production-metrics/`, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  /**
   * @summary Starts production mode for a scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with production execution result
   */
  playProduction(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.post(`${this.apiUrl}${uuid}/play-production/`, {}, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  /**
   * @summary Stops production mode for a scenario by UUID.
   * 
   * @param uuid Scenario identifier
   * 
   * @returns Observable with stop result
   */
  stopProduction(uuid: string): Observable<any> {
    if (isPlatformBrowser(this.platformId)) {
      return this.handleRequest(
        this.http.post(`${this.apiUrl}${uuid}/stop-production/`, {}, { headers: this.getAuthHeaders() })
      );
    }
    return EMPTY;
  }

  /**
   * @summary Deletes a specific anomaly from a scenario's results by UUID.
   * 
   * @param uuid Scenario identifier
   * @param anomalyId Anomaly entry identifier
   * 
   * @returns Observable with deletion status
   */
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
  
  /**
   * @summary Logs the user out by clearing stored tokens.
   */
  logout(): void {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }
}
