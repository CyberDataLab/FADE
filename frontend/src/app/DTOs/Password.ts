/**
 * @summary Interface representing a password change request.
 * 
 * This structure is used when the user wants to update their password.
 * It includes the current password and the new password (entered twice for confirmation).
 */
export interface Password {
    /** @summary User's current password */
    current_password: string;
  
    /** @summary New password chosen by the user */
    new_password: string;
  
    /** @summary Confirmation of the new password (should match `new_password`) */
    confirm_password: string;
  }