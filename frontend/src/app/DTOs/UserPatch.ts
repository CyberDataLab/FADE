/**
 * @summary Interface representing a payload for updating user profile and password.
 * 
 * This structure is typically used in forms where the user can update their
 * username, email, and password. All fields are expected to be provided.
 */
export interface UserPatch {
  /** @summary The new or current username of the user */
  username: string;

  /** @summary The user's current password, required for verification */
  old_password: string;

  /** @summary The new password the user wants to set */
  new_password: string;

  /** @summary Confirmation of the new password (should match `new_password`) */
  confirm_new_password: string;

  /** @summary The user's updated email address */
  email: string;
}