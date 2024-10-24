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
  private usuarioActualSubject: BehaviorSubject<User | null> = new BehaviorSubject<User | null>(null);
  public usuarioActual: Observable<User | null> = this.usuarioActualSubject.asObservable();

  url = 'http://localhost:8000/auth/login';

  constructor(private http: HttpClient, @Inject(PLATFORM_ID) private platformId: Object) {
    if (isPlatformBrowser(this.platformId)) {
      const usuarioLocal = localStorage.getItem('usuarioActual');
      this.usuarioActualSubject = new BehaviorSubject<User | null>(usuarioLocal ? JSON.parse(usuarioLocal) : null);
      this.usuarioActual = this.usuarioActualSubject.asObservable();
    }
   }

   public get valorUsuarioActual(): User | null {
    if (this.usuarioActualSubject.value === null) {
      return null;
    }
    return this.usuarioActualSubject.value;
  }

  getUsuarioActual(){
    return this.usuarioActualSubject.value;
  }

  login(usuarioLogin: UserLogin): Observable<User> | null {
    if (this.usuarioActualSubject.value == null) {
      return this.http.post<User>(this.url, usuarioLogin)
        .pipe(map((usuario: User) => {
          localStorage.setItem('usuarioActual', JSON.stringify(usuario));
          this.usuarioActualSubject.next(usuario);
          return usuario;
        }))
    } else {
      alert("Debe desloguearse para poder realizar el login.");
      return null;
    }
  }

  logout():boolean {
    if (this.usuarioActualSubject.value != null){
      localStorage.removeItem('usuarioActual');
      this.usuarioActualSubject.next(null);
      return true;
    }
    return false;
  }

  modificarUsuario(usuario: User) {
    this.usuarioActualSubject.next(usuario);
    localStorage.setItem('usuarioActual', JSON.stringify(usuario));
  }
}