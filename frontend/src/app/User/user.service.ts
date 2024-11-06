import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { UserRegister } from '../DTOs/UserRegister';
import { User } from '../Entities/User';
import { UserPatch } from '../DTOs/UserPatch';


@Injectable({
  providedIn: 'root'
})
export class UserService {

  url = 'http://localhost:8000/auth';
  url_register = 'http://localhost:8000/auth/register';
  url_send_email= 'http://localhost:8000/auth/send-email';
  url_reset_password= 'http://localhost:8000/auth/reset-password';

  constructor(private http: HttpClient) { }

  register(userRegisterDTO: UserRegister) {
    return this.http.post<User>(this.url_register, userRegisterDTO);
  }

  sendEmail(userPatchDTO: UserPatch) {
    return this.http.post<User>(this.url_send_email, userPatchDTO);
  }
  
  reset_password(newPassword: string, token: string) {
    const body = {
      token: token,
      password: newPassword
    };
    return this.http.post<User>(this.url_reset_password, body);
  }

  getAll() {
    return this.http.get<User[]>(this.url);
  }

  get(id: number){
    return this.http.get<User>(this.url + "/" + id);
  }
}
