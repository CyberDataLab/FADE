import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { UserRegister } from '../DTOs/UserRegister';
import { User } from '../Entities/User';


@Injectable({
  providedIn: 'root'
})
export class UserService {

  url = 'http://localhost:8000/auth/register';

  constructor(private http: HttpClient) { }

  getAll() {
    return this.http.get<User[]>(this.url);
  }

  get(id: number){
    return this.http.get<User>(this.url + "/" + id);
  }

  register(userRegisterDTO: UserRegister) {
    return this.http.post<User>(this.url, userRegisterDTO);
  }
}
