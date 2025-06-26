import { HttpClient } from '@angular/common/http';
import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { User } from '../Entities/User';
import { map } from 'rxjs/operators';
import { UserLogin } from '../DTOs/UserLogin';
import { isPlatformBrowser } from '@angular/common';

@Injectable({
  providedIn: 'root'
})

export class AuthenticationService {
  private actualUserSubject: BehaviorSubject<User | null> = new BehaviorSubject<User | null>(null);
  public actualUser: Observable<User | null> = this.actualUserSubject.asObservable();

  url = 'http://localhost:8000/auth/login';
  urlUser = 'http://localhost:8000/auth/get-user/';
  urlUpdateUser = 'http://localhost:8000/auth/update-user/';
  urlChangePassword = 'http://localhost:8000/auth/change-password/';

  constructor(private http: HttpClient, @Inject(PLATFORM_ID) private platformId: Object) {
    if (isPlatformBrowser(this.platformId)) {
      const usuarioLocal = localStorage.getItem('actual_user');
      this.actualUserSubject = new BehaviorSubject<User | null>(usuarioLocal ? JSON.parse(usuarioLocal) : null);
      this.actualUser = this.actualUserSubject.asObservable();
    }
   }

   public get actualUserValue(): User | null {
    if (this.actualUserSubject.value === null) {
      return null;
    }
    return this.actualUserSubject.value;
  }

  getActualUser(){
    return this.actualUserSubject.value;
  }

  login(usuarioLogin: UserLogin): Observable<User> | null {
    if (this.actualUserSubject.value == null) {
      return this.http.post<any>(this.url, usuarioLogin) 
        .pipe(map((response: any) => {
          if (response.access_token && response.refresh_token) {
            localStorage.setItem('access_token', response.access_token);
            localStorage.setItem('refresh_token', response.refresh_token);
          }
  
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

  modifyUser(user: User) {
    this.actualUserSubject.next(user);
    localStorage.setItem('actual_user', JSON.stringify(user));
  }

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

  updateUser(userData: any) {
    const token = localStorage.getItem('access_token');
    return this.http.put(this.urlUpdateUser, userData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }

  changePassword(passwordData: { current_password: string, new_password: string }) {
    const token = localStorage.getItem('access_token');

    return this.http.post(this.urlChangePassword, passwordData, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  }
  
  
}