// Angular core and common modules
import { HttpClient } from '@angular/common/http';
import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { isPlatformBrowser } from '@angular/common';

// Application-specific models
import { User } from '../Entities/User';
import { UserLogin } from '../DTOs/UserLogin';

/**
 * @summary Service responsible for handling user authentication and session management.
 * 
 * This service provides login, logout, user retrieval, profile update, and password change functionalities.
 */
@Injectable({
  providedIn: 'root'
})
export class AuthenticationService {
  /** @summary Subject holding the current user state */
  private actualUserSubject: BehaviorSubject<User | null> = new BehaviorSubject<User | null>(null);

  /** @summary Public observable to subscribe to current user changes */
  public actualUser: Observable<User | null> = this.actualUserSubject.asObservable();

  /** @summary Backend API endpoints */
  url = 'http://localhost:8000/auth/login';
  urlUser = 'http://localhost:8000/auth/get-user/';
  urlUpdateUser = 'http://localhost:8000/auth/update-user/';
  urlChangePassword = 'http://localhost:8000/auth/change-password/';

  /**
   * @summary Initializes user state from localStorage in browser environment.
   * 
   * @param http Angular HttpClient to communicate with backend
   * @param platformId Platform identifier to check for browser context
   */
  constructor(private http: HttpClient, @Inject(PLATFORM_ID) private platformId: Object) {
    // Load user from localStorage only in browser environment
    if (isPlatformBrowser(this.platformId)) {
      const usuarioLocal = localStorage.getItem('actual_user');
      this.actualUserSubject = new BehaviorSubject<User | null>(usuarioLocal ? JSON.parse(usuarioLocal) : null);
      this.actualUser = this.actualUserSubject.asObservable();
    }
   }

   /**
   * @summary Gets the current user synchronously.
   * 
   * @returns The currently logged-in user or `null`
   */
   public get actualUserValue(): User | null {
    if (this.actualUserSubject.value === null) {
      return null;
    }
    return this.actualUserSubject.value;
  }

  /**
   * @summary Alternative method to access the current user.
   */
  getActualUser(){
    return this.actualUserSubject.value;
  }

  /**
   * @summary Authenticates user and stores tokens and user data.
   * 
   * If login is successful, stores tokens and user in `localStorage`,
   * updates reactive subject, and returns the user as observable.
   * 
   * @param usuarioLogin Object containing `username` and `password`
   * @returns Observable with authenticated user or `null` if already logged in
   */
  login(usuarioLogin: UserLogin): Observable<User> | null {
    if (this.actualUserSubject.value == null) {
      return this.http.post<any>(this.url, usuarioLogin) 
        .pipe(map((response: any) => {
          // Save tokens to localStorage
          if (response.access_token && response.refresh_token) {
            localStorage.setItem('access_token', response.access_token);
            localStorage.setItem('refresh_token', response.refresh_token);
          }
  
          // Save user to localStorage and update subject
          const usuario: User = response.user; 
          localStorage.setItem('actual_user', JSON.stringify(usuario));
          this.actualUserSubject.next(usuario);
          return usuario;
        }));
    } else {
      alert("You must be logged out in order to login.");
      return null;
    }
  }
  
  // Logout method: clear localStorage and reset user subject
  logout():boolean {
    if (this.actualUserSubject.value != null){
      localStorage.removeItem('actual_user');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      this.actualUserSubject.next(null);
      return true;
    }
    return false;
  }

  // Updates the local user manually
  modifyUser(user: User) {
    this.actualUserSubject.next(user);
    localStorage.setItem('actual_user', JSON.stringify(user));
  }

  // Fetches user information from backend using access token
  getInfoActualUser(): Observable<User> {
    const token = localStorage.getItem('access_token');
  
    return this.http.get<any>(this.urlUser, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }).pipe(
      map((response: any) => {
        const user: User = response.user;
        this.actualUserSubject.next(user);
        localStorage.setItem('actual_user', JSON.stringify(user));
        return user;
      })
    );
  }

  // Sends PUT request to update user profile
  updateUser(userData: any) {
    const token = localStorage.getItem('access_token');
    return this.http.put(this.urlUpdateUser, userData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  // Sends POST request to update user password
  changePassword(passwordData: { current_password: string, new_password: string }) {
    const token = localStorage.getItem('access_token');

    return this.http.post(this.urlChangePassword, passwordData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }
  
  
}