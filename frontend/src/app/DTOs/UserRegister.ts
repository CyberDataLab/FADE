/**
 * @summary Interface representing the payload required to register a new user.
 * 
 * This structure is used when an administrator creates a new user account,
 * requiring admin credentials for authorization and full user details.
 */
export interface UserRegister {
  /** @summary Administrator's username, used to authorize the registration request */
  admin_username: string;

  /** @summary Administrator's password, used to verify permissions */
  admin_password: string;

  /** @summary Desired username for the new user account */
  username: string;

  /** @summary Password for the new user account */
  password: string;

  /** @summary Confirmation of the new password (must match `password`) */
  confirm_password: string;

  /** @summary First name of the user */
  first_name: string;

  /** @summary Last name of the user */
  last_name: string;

  /** @summary Email address associated with the new user account */
  email: string;
}