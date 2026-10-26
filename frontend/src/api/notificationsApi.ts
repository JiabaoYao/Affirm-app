import { baseApi } from "./baseApi";
import { qs } from "./qs";
import type { Notification, NotificationPage } from "./types";

export const notificationsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    notifications: build.query<NotificationPage, { page?: number; size?: number; unread_only?: boolean }>({
      query: (params) => `/notifications${qs({ ...params })}`,
      providesTags: ["Notification"],
    }),
    markRead: build.mutation<Notification, number>({
      query: (id) => ({ url: `/notifications/${id}/read`, method: "POST" }),
      invalidatesTags: ["Notification"],
    }),
    markAllRead: build.mutation<void, void>({
      query: () => ({ url: "/notifications/read-all", method: "POST" }),
      invalidatesTags: ["Notification"],
    }),
  }),
});

export const { useNotificationsQuery, useMarkReadMutation, useMarkAllReadMutation } = notificationsApi;
