// Angular and HTTP modules
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

// Application-specific models and DTOs
import { UserRegister } from '../DTOs/UserRegister';
import { User } from '../Entities/User';
import { UserPatch } from '../DTOs/UserPatch';

/**
 * @summary Service for managing user-related operations.
 * 
 * This includes registration, password reset, email sending, and retrieval of user data.
 */
@Injectable({
  providedIn: 'root'
})
export class UserService {

  /** @summary Base URL for user-related endpoints */
  url = 'http://localhost:8000/auth';

  /** @summary Endpoint to register a new user */
  url_register = 'http://localhost:8000/auth/register';

  /** @summary Endpoint to send a password reset email */
  url_send_email = 'http://localhost:8000/auth/send-email';

  /** @summary Endpoint to reset password using a token */
  url_reset_password = 'http://localhost:8000/auth/reset-password';

  /**
   * @summary Injects the HttpClient service.
   * 
   * @param http Angular HttpClient used for sending HTTP requests
   */
  constructor(private http: HttpClient) {}

  /**
   * @summary Registers a new user with admin authorization.
   * 
   * @param userRegisterDTO Data required to create the new user
   * @returns Observable with the created user
   */
  register(userRegisterDTO: UserRegister) {
    return this.http.post<User>(this.url_register, userRegisterDTO);
  }

  /**
   * @summary Sends a password reset email to the user.
   * 
   * @param userPatchDTO Contains the email and possibly other verification fields
   * @returns Observable with the user (or result message)
   */
  sendEmail(userPatchDTO: UserPatch) {
    return this.http.post<User>(this.url_send_email, userPatchDTO);
  }
  
  /**
   * @summary Resets a user's password using a token.
   * 
   * @param newPassword The new password to be set
   * @param token Reset token received via email
   * @returns Observable with the updated user or confirmation
   */
  reset_password(newPassword: string, token: string) {
    const body = {
      token: token,
      password: newPassword
    };
    return this.http.post<User>(this.url_reset_password, body);
  }

  /**
   * @summary Fetches all registered users.
   * 
   * @returns Observable with a list of users
   */
  getAll() {
    return this.http.get<User[]>(this.url);
  }

  /**
   * @summary Fetches a specific user by ID.
   * 
   * @param id Unique identifier of the user
   * @returns Observable with the corresponding user
   */
  get(id: number){
    return this.http.get<User>(this.url + "/" + id);
  }
}
