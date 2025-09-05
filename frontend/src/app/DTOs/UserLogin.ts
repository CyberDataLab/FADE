/**
 * @summary Interface representing user credentials used for login.
 * 
 * This structure is sent to the backend authentication endpoint to request access tokens.
 */
export interface UserLogin {
    /** @summary The username or email address used to identify the user */
    username: string;
  
    /** @summary The user's plaintext password for authentication */
    password: string;
  }